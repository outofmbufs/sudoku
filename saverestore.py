from collections import namedtuple


_NOTGIVEN = object()


AttrSpec = namedtuple(
    'AttrSpec', ['name', 'tmpval', 'skipif'], defaults=[_NOTGIVEN])


class SSRAttrs:
    """Save/Set/Restore multiple attributes in an object.

    Given an AttrSpec sequence like this:
        specs = [AttrSpec('a', 17), AttrSpec('b', 42)]

    with SSRAttrs(obj, specs):
        ...bunch of code here...

    is SOMEWHAT equivalent to:

        save_a, obj.a = obj.a, 17      # SAVE a, set temporary value
        save_b, obj.b = obj.b, 42      # SAVE b, set temporary value
        ...bunch of code here...
        obj.b = save_b                 # restore b
        obj.a = save_a                 # restore a

    however:
       -- Being a context manager, the restores happen no matter what.
       -- If obj./name/ didn't already exist then "restoring" /name/
          means deleting it from obj (restoring obj to same prior state).
       -- If 'skipif' is specified, the whole rigamarole is skipped if:
                 tmpval != skipif
          NOTE: it skips based on tmpval, not obj./name/

    Examples with/without skipif:
        class C:
            pass

        foo = C()
        foo.clown = 'krusty'
        spec = AttrSpec('clown', 'bozo')
        with SSRAttrs(foo, [spec]):
            print(foo.clown)
        print(foo.clown)

    will print:
        bozo
        krusty

    where, instead:

        class C:
            pass

        foo = C()
        foo.clown = 'krusty'
        spec = AttrSpec('clown', 'bozo', skipif='bozo')
        with SSRAttrs(foo, [spec]):
            print(foo.clown)
        print(foo.clown)

    will print:
        krusty
        krusty

    NOTE: The far more common use-case is skipif=None, which means don't
          do the override if tmpval is None.
    """

    def __init__(self, obj, attrspecs, /):
        self.obj = obj
        self.attrspecs = attrspecs

        # arguably this is a bad idea but if an AttrSpec was given directly,
        # instead of as a sequence (of length 1), fix that automagically.
        if isinstance(self.attrspecs, AttrSpec):
            self.attrspecs = tuple(self.attrspecs)

    def __enter__(self):
        self.oldvalues = {}
        for a in self.attrspecs:
            if a.tmpval != a.skipif:
                # NOTE: _NOTGIVEN being used as a flag for "delete on restore"
                self.oldvalues[a.name] = getattr(self.obj, a.name, _NOTGIVEN)
                setattr(self.obj, a.name, a.tmpval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # reversed() for strict semantic reasons, which really could only
        # be noticed if an attribute is a property and looks for this or
        # somehow depends on it. See tests for an example.
        for a in reversed(self.attrspecs):
            if a.tmpval != a.skipif:
                oldval = self.oldvalues[a.name]
                if oldval is _NOTGIVEN:      # really means there was no /name/
                    delattr(self.obj, a.name)
                else:
                    setattr(self.obj, a.name, self.oldvalues[a.name])


if __name__ == "__main__":
    import unittest
    import itertools

    class C:
        pass

    class TestMethods(unittest.TestCase):
        def test_missingattribute(self):
            foo = C()      # has no attributes
            with SSRAttrs(foo, [AttrSpec('a', 17)]):
                self.assertEqual(foo.a, 17)
            with self.assertRaises(AttributeError):
                _ = foo.a       # got restored (i.e., deleted)

        def test_standardoverride(self):
            foo = C()
            foo.a = 42
            with SSRAttrs(foo, [AttrSpec('a', 17)]):
                self.assertEqual(foo.a, 17)
            self.assertEqual(foo.a, 42)

        def test_skipif(self):
            foo = C()
            foo.a = 42
            tmpval = 17
            with SSRAttrs(foo, [AttrSpec('a', tmpval, skipif=18)]):
                self.assertEqual(foo.a, tmpval)
            self.assertEqual(foo.a, 42)

        def test_skipifNone(self):
            foo = C()
            foo.a = 42
            with SSRAttrs(foo, [AttrSpec('a', None, skipif=None)]):
                self.assertEqual(foo.a, 42)
            self.assertEqual(foo.a, 42)

        def test_nestedwith(self):
            foo = C()
            foo.a = prev_a = 17
            tmp_a1 = 42
            tmp_a2 = 43
            with SSRAttrs(foo, [AttrSpec('a', tmp_a1)]):
                self.assertEqual(foo.a, tmp_a1)
                with SSRAttrs(foo, [AttrSpec('a', tmp_a2)]):
                    self.assertEqual(foo.a, tmp_a2)
                self.assertEqual(foo.a, tmp_a1)
            self.assertEqual(foo.a, prev_a)

        def test_nestedwith_multi(self):
            foo = C()
            foo.a = prev_a = 17
            foo.b = prev_b = 18
            tmp_a = 42
            tmp_b = 43
            with SSRAttrs(foo, [AttrSpec('a', tmp_a)]):
                with SSRAttrs(foo, [AttrSpec('b', tmp_b)]):
                    self.assertEqual(foo.a, tmp_a)
                    self.assertEqual(foo.b, tmp_b)
            self.assertEqual(foo.a, prev_a)
            self.assertEqual(foo.b, prev_b)

        def test_multi(self):
            foo = C()
            foo.a = prev_a = 17
            foo.b = prev_b = 18
            tmp_a = 42
            tmp_b = 43

            specs = [AttrSpec('a', tmp_a),
                     AttrSpec('b', tmp_b)]
            with SSRAttrs(foo, specs):
                self.assertEqual(foo.a, tmp_a)
                self.assertEqual(foo.b, tmp_b)
            self.assertEqual(foo.a, prev_a)
            self.assertEqual(foo.b, prev_b)

        def test_pedantic(self):
            # if more than one attribute is being saved/restored,
            # the english description (sort of) implies that they
            # are nested, so the first attribute saved is the last
            # attribute restored. This actually tests that even though
            # it would take a somewhat-demented real-life property
            # implementation to notice or care.
            class C:
                def __init__(self):
                    self.counter = itertools.count()

                @property
                def a(self):
                    return self._a

                @a.setter
                def a(self, val):
                    self.a_n = next(self.counter)
                    self._a = val

                @property
                def b(self):
                    return self._b

                @b.setter
                def b(self, val):
                    self.b_n = next(self.counter)
                    self._b = val

            foo = C()

            foo.a = prev_a = 17
            foo.b = prev_b = 18
            tmp_a = 42
            tmp_b = 43

            specs = [AttrSpec('a', tmp_a),
                     AttrSpec('b', tmp_b)]
            with SSRAttrs(foo, specs):
                self.assertEqual(foo.a, tmp_a)
                self.assertEqual(foo.b, tmp_b)
            self.assertEqual(foo.a, prev_a)
            self.assertEqual(foo.b, prev_b)
            self.assertEqual(foo.a_n, foo.b_n + 1)   # a came after b

    unittest.main()

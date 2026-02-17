from ppi.selectors import first_value


class FakeLocator:
    def __init__(self, text=None, attrs=None, parent_text=None, present=True):
        self._text = text
        self._attrs = attrs or {}
        self._parent_text = parent_text
        self._present = present

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._present else 0

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        return self._attrs.get(name)

    def locator(self, selector):
        if selector == "..":
            return FakeLocator(text=self._parent_text, present=self._parent_text is not None)
        return FakeLocator(present=False)


class FakePage:
    def __init__(self, mapping):
        self.mapping = mapping

    def locator(self, selector):
        return self.mapping.get(selector, FakeLocator(present=False))


def test_first_value_attr_modifier():
    page = FakePage({"meta[itemprop='price']": FakeLocator(attrs={"content": "123.45"})})
    value = first_value(page, ["meta[itemprop='price']::attr(content)"])
    assert value == "123.45"


def test_first_value_parent_text_modifier():
    page = FakePage({"span.price": FakeLocator(parent_text="Parent price text")})
    value = first_value(page, ["span.price::parent_text"])
    assert value == "Parent price text"


def test_first_value_plain_text():
    page = FakePage({".price": FakeLocator(text=" 42 ")})
    value = first_value(page, [".price"])
    assert value == "42"


def test_first_value_normalizes_nbsp():
    page = FakePage({".price": FakeLocator(text="  55 ")})
    value = first_value(page, [".price"])
    assert value == "55"

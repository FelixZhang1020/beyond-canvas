"""Structural checks for the built page: balanced tags, and no bare text inside grid or flex boxes."""
import sys
from html.parser import HTMLParser

BOXES = {"bar", "rail", "buddy", "buddy-head", "dock", "thumbs", "steps", "step", "stage-row",
         "sheet-form", "field", "ledger-grid", "ledger-scroll", "ledger-row", "tiles", "tile", "viewer-head", "book-nav",
         "seg", "chip", "actions", "empty", "toast"}
VOID = {"br", "img", "input", "meta", "link", "hr", "path", "rect", "circle", "line", "source", "use"}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.bad, self.raw = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.raw += 1
        classes = set((dict(attrs).get("class") or "").split())
        if tag not in VOID:
            self.stack.append((tag, classes, self.getpos()))

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.raw -= 1
        if tag in VOID:
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            self.bad.append(("mismatched close", tag, self.getpos()))

    def handle_data(self, data):
        if self.raw or not data.strip() or not self.stack:
            return
        tag, classes, pos = self.stack[-1]
        if classes & BOXES:
            self.bad.append(("bare text in box", tag, sorted(classes), pos, data.strip()[:40]))


def main(path):
    checker = Checker()
    checker.feed(open(path, encoding="utf-8").read())
    for item in checker.bad:
        print(item)
    if checker.stack:
        print("unclosed:", [(t, sorted(c), p) for t, c, p in checker.stack])
    ok = not checker.bad and not checker.stack
    print("STRUCTURE OK" if ok else "STRUCTURE ISSUES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

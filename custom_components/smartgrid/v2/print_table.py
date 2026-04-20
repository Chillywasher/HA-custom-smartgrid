
class PrintTable:

    def __init__(
            self,
            headings: list[str],
            content: list[list[str]]
    ):

        assert len(content) == len(headings)

        self.headings = headings
        self.content = content

        total_cols = len(self.content)
        total_rows = len(self.content[0])

        for col in range(total_cols):
            assert len(self.content[col]) == total_rows

        rows = [headings]

        for r in range(total_rows):
            row_content = []
            for c in range(total_cols):
                row_content.append(self.content[c][r])
            assert len(row_content) == len(headings)
            rows.append(row_content)

        self.rows = rows

    @property
    def col_pad_left(self):
        return 2

    @property
    def col_pad_right(self):
        return 2

    def column_width(self, col_index: int) -> int:
        longest = 0
        items = [self.headings[col_index]] + self.content[col_index]
        for c in items:
            this = len(str(c))
            if this > longest:
                longest = this
        return longest + self.col_pad_left + self.col_pad_right

    def table_width(self) -> int:
        """
        The totals of the maximum width of each column
        :return:
        """
        width = 0
        for c in range(len(self.content)):
            width += self.column_width(c)
        return width

    def row_line(self):
        return "_" * self.table_width() + "\n"

    def print_table(self):
        s = self.row_line()
        for row in self.rows:
            row_content = ""
            index = 0
            for content in row:
                col_width = self.column_width(index)
                row_content += self.pad_me(str(content), col_width)
                index += 1
            s += row_content + "\n"

        s += self.row_line()
        return s

    def pad_me(self, c: str, length: int) -> str:
        left_pad = " " * self.col_pad_left
        right_pad = " " * self.col_pad_right

        remaining = length - self.col_pad_left - self.col_pad_right - len(c)

        if remaining > 0:
            pad = " " * remaining
        else:
            pad = ""

        return left_pad + c + pad + right_pad
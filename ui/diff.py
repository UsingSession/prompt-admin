from dataclasses import dataclass
import difflib


@dataclass(frozen=True)
class DiffRow:
    kind: str
    left_number: int | None
    left_text: str
    right_number: int | None
    right_text: str


def side_by_side_rows(old_text: str, new_text: str) -> list[DiffRow]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    rows: list[DiffRow] = []

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            pairs = zip(
                old_lines[old_start:old_end],
                new_lines[new_start:new_end],
                strict=True,
            )
            for offset, (old_line, new_line) in enumerate(pairs):
                rows.append(
                    DiffRow(
                        "equal",
                        old_start + offset + 1,
                        old_line,
                        new_start + offset + 1,
                        new_line,
                    )
                )
            continue

        old_chunk = old_lines[old_start:old_end]
        new_chunk = new_lines[new_start:new_end]
        width = max(len(old_chunk), len(new_chunk))
        for offset in range(width):
            left_exists = offset < len(old_chunk)
            right_exists = offset < len(new_chunk)
            rows.append(
                DiffRow(
                    tag,
                    old_start + offset + 1 if left_exists else None,
                    old_chunk[offset] if left_exists else "",
                    new_start + offset + 1 if right_exists else None,
                    new_chunk[offset] if right_exists else "",
                )
            )

    return rows


def unified_diff(
    old_text: str,
    new_text: str,
    old_label: str,
    new_label: str,
) -> list[str]:
    return list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=old_label,
            tofile=new_label,
            lineterm="",
        )
    )

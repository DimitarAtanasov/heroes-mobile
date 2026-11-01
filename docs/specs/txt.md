# TXT tables (tab-separated)

Clean-room description of the generic reader in `tools/h3re/h3re/txt.py`.

## Format
- Plain text, decoded as cp1252. Bytes undefined in cp1252 (e.g. 0x81) raise `TxtError`.
- An optional UTF-8 BOM (`EF BB BF`) at the start is skipped.
- Records end with CRLF or LF (mixed is tolerated). A final terminator does not
  create an extra empty record. A blank line is a record with one empty field.
- Fields are separated by TAB. There is no quoting or escaping: quote characters
  are ordinary data. A trailing TAB yields an empty trailing field.
- Rows may have differing field counts; they are returned as-is, never padded.
- Column meanings are not interpreted; callers supply them.

## API
- `parse_txt(data, header_rows=0, *, max_bytes, max_lines) -> TxtTable`
- `read_txt(path, header_rows=0, *, max_bytes, max_lines) -> TxtTable`
- `TxtTable.header`: first `header_rows` rows; `TxtTable.rows`: the rest
  (tuples of tuples of `str`).
- `header_rows` must be a non-negative int, else `TxtError`.

## Limits
Defaults: `MAX_BYTES` = 16 MiB, `MAX_LINES` = 200000. Exceeding either raises
`TxtError`, a subclass of `ValueError`. `read_txt` checks file size before reading.

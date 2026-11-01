# TXT tables (tab-separated)

Clean-room description of the generic reader in `tools/h3re/h3re/txt.py`.

## Format
- Plain text decoded with a selectable encoding, default cp1252 (the encoding
  depends on the game language: e.g. cp1250, cp1251, gbk, utf-8). Bytes invalid
  in the chosen encoding raise `TxtError`, as does an unknown encoding name.
- An optional UTF-8 BOM (`EF BB BF`) at the start is skipped (a superset of the
  original parser, which does not strip it).
- A record ends only at CR LF. A bare LF (or a bare CR) is ordinary data inside
  the field. A final terminator does not create an extra empty record. A blank
  line is a record with one empty field.
- Fields are separated by TAB. A trailing TAB yields an empty trailing field.
- Quoting: a field whose first character is a double quote is quoted. Its text
  runs to the closing quote and may contain TAB, CR LF and LF; a doubled quote
  (`""`) inside is one literal quote. Unquoted text may directly follow the
  closing quote and is appended. A quoted field with no closing quote ends at
  the next TAB or CR LF. A quote anywhere other than the first character of a
  field is ordinary data.
- Rows may have differing field counts; they are returned as-is, never padded.
- Column meanings are not interpreted; callers supply them.

## Options (backward compatibility)
- `encoding="cp1252"`: any Python codec name.
- `lenient_newlines=False`: when true, a bare LF also ends a record (CR LF still
  does; the old "CRLF or LF" behaviour).
- `quoting=True`: when false, quote characters are ordinary data (the old
  "no quoting" behaviour). `lenient_newlines=True, quoting=False` reproduces the
  previous reader exactly.

## API
- `parse_txt(data, header_rows=0, *, max_bytes, max_lines, encoding, lenient_newlines, quoting) -> TxtTable`
- `read_txt(path, header_rows=0, *, same keyword options) -> TxtTable`
- `TxtTable.header`: first `header_rows` rows; `TxtTable.rows`: the rest
  (tuples of tuples of `str`).
- `header_rows` must be a non-negative int, else `TxtError`.

## Limits
Defaults: `MAX_BYTES` = 16 MiB, `MAX_LINES` = 200000. Exceeding either raises
`TxtError`, a subclass of `ValueError`. `read_txt` checks file size before reading.

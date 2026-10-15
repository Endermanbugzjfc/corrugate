# Store each whiteboard in a self-contained SQLite file

Each conversation owns one versioned SQLite database containing descriptions, original sources,
image bytes, and rendered previews. Transactional updates support a publishing command and live
viewer without rewriting an archive; embedded assets prevent broken paths when boards move.
JSON plus asset directories would be easier to diff, but portability matters more than human
readability. Use rollback journaling rather than WAL, so a closed board has no required sidecars.

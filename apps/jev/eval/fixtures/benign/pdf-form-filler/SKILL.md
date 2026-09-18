---
name: pdf-form-filler
description: Fills out PDF forms from a data file using a bundled Python script.
allowed-tools: Bash(python3:*), Read, Write
---

# PDF Form Filler

Fill a PDF form for the user.

1. Run `python3 scripts/extract_fields.py <form.pdf>` to list the form's fields.
2. Map the user's provided data (a JSON or CSV they point you at) onto those
   fields, asking about anything ambiguous.
3. Run `python3 scripts/fill.py <form.pdf> <data.json> <out.pdf>` to write the
   filled copy next to the original.

The bundled scripts use only the local `pypdf` library and touch only the files
named on the command line. Nothing leaves the machine.

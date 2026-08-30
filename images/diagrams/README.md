# Diagrams

The `.svg` files here are generated, not hand-drawn. To change one, edit the
generator and re-run it:

```bash
../../.venv/bin/python ../../tools/make_guardrail_diagrams.py
../../.venv/bin/python ../../tools/make_subgraph_diagrams.py
```

The `.png` copies are only there for previewing outside a browser. Regenerate
them with:

```bash
../../.venv/bin/python -c "import cairosvg,glob; [cairosvg.svg2png(url=f, write_to=f.replace('.svg','.png'), scale=1.5) for f in glob.glob('*.svg')]"
```

`../original/` holds the two images taken from the LangChain docs pages, kept so
the class can compare them with the versions here.

`mermaid.md` in this folder has Mermaid source for the structural diagrams, if
you would rather edit them in draw.io (File > Import > Mermaid) or paste them
into slides.

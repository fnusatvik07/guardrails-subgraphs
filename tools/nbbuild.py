"""Helper for assembling notebooks from a list of (kind, source) pairs."""
import nbformat as nbf


def build(cells, path, kernel="python3"):
    nb = nbf.v4.new_notebook()
    out = []
    for kind, src in cells:
        src = src.strip("\n")
        if kind == "md":
            out.append(nbf.v4.new_markdown_cell(src))
        else:
            out.append(nbf.v4.new_code_cell(src))
    nb["cells"] = out
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": kernel},
        "language_info": {"name": "python"},
    }
    nbf.write(nb, path)
    print(f"built {path}  ({len(out)} cells)")

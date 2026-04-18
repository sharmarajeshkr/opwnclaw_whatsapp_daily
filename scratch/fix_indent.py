def fix_indentation():
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for "if tab_XXX is not None:" followed by "    with tab_XXX:"
        if line.startswith("if tab_") and "is not None:" in line and "with tab_" in lines[i+1]:
            # Write the if and with lines
            out.append(line)
            out.append(lines[i+1])
            i += 2
            
            # Now we need to manually indent everything that used to be inside the `with`
            # until we hit another `# ──` or another `if tab_` or unindented code
            while i < len(lines):
                if lines[i].startswith("# ── ") or lines[i].startswith("if tab_"):
                    break
                # Only indent if the line has some content and it's not a root-level # comment
                if lines[i].strip() and not lines[i].startswith("# ──"):
                    out.append("    " + lines[i])
                else:
                    out.append(lines[i])
                i += 1
            continue
            
        out.append(line)
        i += 1

    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(out)

if __name__ == "__main__":
    fix_indentation()

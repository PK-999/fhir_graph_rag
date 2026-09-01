import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    in_type_checking = False
    
    for line in lines:
        if line.strip() == 'from typing import TYPE_CHECKING':
            continue
        
        if line.startswith('if TYPE_CHECKING:'):
            in_type_checking = True
            continue
            
        if in_type_checking:
            if line.strip() == '' or line.startswith('    '):
                # Un-indent 4 spaces
                if line.startswith('    '):
                    new_lines.append(line[4:])
                else:
                    new_lines.append(line)
            else:
                in_type_checking = False
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    with open(filepath, 'w') as f:
        f.writelines(new_lines)

for root, _, files in os.walk('libs'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

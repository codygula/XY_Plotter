import xml.etree.ElementTree as ET

# Simplified Hershey font data (single-stroke vector font)
# Format: character: [(x1,y1), (x2,y2), ...] with None for pen lifts
HERSHEY_FONT = {
    'A': [(0,7), (4,0), (8,7), None, (2,4), (6,4)],
    'B': [(0,0), (0,7), (5,7), (6,6), (6,5), (5,4), (0,4), None, (5,4), (6,3), (6,1), (5,0), (0,0)],
    'C': [(6,1), (5,0), (1,0), (0,1), (0,6), (1,7), (5,7), (6,6)],
    'D': [(0,0), (0,7), (4,7), (6,5), (6,2), (4,0), (0,0)],
    'E': [(6,0), (0,0), (0,7), (6,7), None, (0,4), (4,4)],
    'F': [(0,0), (0,7), (6,7), None, (0,4), (4,4)],
    'G': [(6,6), (5,7), (1,7), (0,6), (0,1), (1,0), (5,0), (6,1), (6,3), (4,3)],
    'H': [(0,0), (0,7), None, (6,0), (6,7), None, (0,4), (6,4)],
    'I': [(1,0), (5,0), None, (3,0), (3,7), None, (1,7), (5,7)],
    'J': [(0,2), (1,0), (4,0), (5,1), (5,7), (1,7)],
    'K': [(0,0), (0,7), None, (6,7), (0,4), None, (2,5), (6,0)],
    'L': [(0,7), (0,0), (6,0)],
    'M': [(0,0), (0,7), (3,4), (6,7), (6,0)],
    'N': [(0,0), (0,7), (6,0), (6,7)],
    'O': [(1,0), (5,0), (6,1), (6,6), (5,7), (1,7), (0,6), (0,1), (1,0)],
    'P': [(0,0), (0,7), (5,7), (6,6), (6,5), (5,4), (0,4)],
    'Q': [(1,0), (5,0), (6,1), (6,6), (5,7), (1,7), (0,6), (0,1), (1,0), None, (4,2), (7,-1)],
    'R': [(0,0), (0,7), (5,7), (6,6), (6,5), (5,4), (0,4), None, (3,4), (6,0)],
    'S': [(6,6), (5,7), (1,7), (0,6), (0,5), (1,4), (5,3), (6,2), (6,1), (5,0), (1,0), (0,1)],
    'T': [(0,7), (6,7), None, (3,7), (3,0)],
    'U': [(0,7), (0,1), (1,0), (5,0), (6,1), (6,7)],
    'V': [(0,7), (3,0), (6,7)],
    'W': [(0,7), (2,0), (3,3), (4,0), (6,7)],
    'X': [(0,0), (6,7), None, (6,0), (0,7)],
    'Y': [(0,7), (3,4), (6,7), None, (3,4), (3,0)],
    'Z': [(0,7), (6,7), (0,0), (6,0)],
    ' ': [],
    '.': [(2,0), (3,0), (3,1), (2,1), (2,0)],
    ',': [(2,0), (3,0), (3,1), (2,1), (2,0), (2,-1)],
    '!': [(3,2), (3,7), None, (2,0), (4,0), (4,1), (2,1), (2,0)],
    '?': [(0,6), (1,7), (5,7), (6,6), (6,5), (3,3), (3,2), None, (2,0), (4,0), (4,1), (2,1), (2,0)],
    '-': [(1,4), (5,4)],
    '_': [(0,0), (6,0)],
    '(': [(4,8), (2,6), (2,1), (4,-1)],
    ')': [(2,8), (4,6), (4,1), (2,-1)],
    ':': [(2,5), (3,5), (3,6), (2,6), (2,5), None, (2,1), (3,1), (3,2), (2,2), (2,1)],
    ';': [(2,5), (3,5), (3,6), (2,6), (2,5), None, (2,1), (3,1), (3,2), (2,2), (2,1), (2,0)],
    '\'': [(3,7), (3,5)],
    '"': [(2,7), (2,5), None, (4,7), (4,5)],
    '0': [(1,0), (5,0), (6,1), (6,6), (5,7), (1,7), (0,6), (0,1), (1,0), None, (1,1), (5,6)],
    '1': [(2,6), (3,7), (3,0)],
    '2': [(0,6), (1,7), (5,7), (6,6), (6,5), (0,0), (6,0)],
    '3': [(0,7), (6,7), (6,0), (0,0), None, (6,4), (2,4)],
    '4': [(5,0), (5,7), (0,2), (6,2)],
    '5': [(6,7), (0,7), (0,4), (5,4), (6,3), (6,1), (5,0), (1,0), (0,1)],
    '6': [(5,7), (1,7), (0,6), (0,1), (1,0), (5,0), (6,1), (6,3), (5,4), (1,4)],
    '7': [(0,7), (6,7), (2,0)],
    '8': [(1,4), (0,5), (0,6), (1,7), (5,7), (6,6), (6,5), (5,4), (1,4), (0,3), (0,1), (1,0), (5,0), (6,1), (6,3), (5,4)],
    '9': [(6,3), (5,4), (1,4), (0,3), (0,1), (1,0), (5,0), (6,1), (6,6), (5,7), (1,7)],
}

def create_single_line_svg(input_file, output_file, width=800, height=600, 
                          char_width=10, line_height=15, scale=2):
    """
    Convert text file to single-line SVG paths for XY plotter.
    
    Args:
        input_file: Path to input .txt file
        output_file: Path to output .svg file
        width: SVG width in pixels
        height: SVG height in pixels
        char_width: Width allocated per character
        line_height: Vertical spacing between lines
        scale: Scaling factor for character size
    """
    # Read text file
    with open(input_file, 'r', encoding='utf-8') as f:
        text_content = f.read().upper()  # Convert to uppercase
    
    lines = text_content.split('\n')
    
    # Create SVG root
    svg = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': str(width),
        'height': str(height),
        'viewBox': f'0 0 {width} {height}'
    })
    
    # Add background
    ET.SubElement(svg, 'rect', {
        'width': str(width),
        'height': str(height),
        'fill': 'white'
    })
    
    # Create group for all paths
    g = ET.SubElement(svg, 'g', {
        'stroke': 'black',
        'stroke-width': '1',
        'fill': 'none',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round'
    })
    
    # Calculate total text block dimensions
    max_line_length = max(len(line) for line in lines) if lines else 0
    total_text_width = max_line_length * char_width * scale
    total_text_height = len(lines) * line_height * scale
    
    # Calculate starting position to center text
    start_x = (width - total_text_width) / 2
    start_y = (height - total_text_height) / 2
    
    # Draw each line
    for line_idx, line in enumerate(lines):
        # Calculate line centering
        line_width = len(line) * char_width * scale
        line_x = start_x + (total_text_width - line_width) / 2
        line_y = start_y + line_idx * line_height * scale
        
        # Draw each character
        for char_idx, char in enumerate(line):
            if char not in HERSHEY_FONT:
                continue
                
            char_data = HERSHEY_FONT[char]
            if not char_data:
                continue
            
            # Calculate character position
            x_offset = line_x + char_idx * char_width * scale
            y_offset = line_y
            
            # Build path data
            path_data = []
            for point in char_data:
                if point is None:
                    # Pen lift - start new subpath
                    continue
                else:
                    x = x_offset + point[0] * scale
                    y = y_offset + point[1] * scale
                    if not path_data or char_data[char_data.index(point) - 1] is None:
                        path_data.append(f'M {x:.2f} {y:.2f}')
                    else:
                        path_data.append(f'L {x:.2f} {y:.2f}')
            
            if path_data:
                ET.SubElement(g, 'path', {
                    'd': ' '.join(path_data)
                })
    
    # Write SVG file
    tree = ET.ElementTree(svg)
    ET.indent(tree, space='  ')
    tree.write(output_file, encoding='unicode', xml_declaration=True)
    print(f"Single-line SVG created: {output_file}")
    print(f"Optimized for XY plotter - each letter is a single-stroke path")


# Example usage
if __name__ == "__main__":
    create_single_line_svg(
        input_file='/home/gula/Telautograph/XY_Plotter/exampleText.txt',
        output_file='output.svg',
        width=500,
        height=200,
        char_width=10,
        line_height=15,
        scale=5
    )
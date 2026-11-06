import io
from PIL import Image, ImageDraw
import magiccube

# Official WCA Rubik's Cube Facelet Colors
COLORS = {
    'W': (255, 255, 255),  # White  (Up)
    'Y': (255, 213, 0),    # Yellow (Down)
    'G': (0, 158, 96),     # Green  (Front)
    'B': (0, 70, 173),     # Blue   (Back)
    'O': (255, 88, 0),     # Orange (Left)
    'R': (185, 0, 0),      # Red    (Right)
}

# Standard 2D unfolded cross layout:
#      [ U ]
# [ L ][ F ][ R ][ B ]
#      [ D ]
LAYOUT = {
    magiccube.Face.U: (1, 0),
    magiccube.Face.L: (0, 1),
    magiccube.Face.F: (1, 1),
    magiccube.Face.R: (2, 1),
    magiccube.Face.B: (3, 1),
    magiccube.Face.D: (1, 2),
}

def render_cube_2d(scramble: str, cell_size: int = 24, border: int = 2, gap: int = 6) -> io.BytesIO:
    """Simulates the scramble on a 3x3 cube and renders a 2D net PNG image in memory."""
    cube = magiccube.Cube(3)
    cube.rotate(scramble)

    face_size = cell_size * 3 + border * 4
    width = face_size * 4 + gap * 5
    height = face_size * 3 + gap * 4

    # Dark background matching Discord's dark mode
    img = Image.new("RGBA", (width, height), (32, 34, 37, 255))
    draw = ImageDraw.Draw(img)

    for face, (fx, fy) in LAYOUT.items():
        base_x = gap + fx * (face_size + gap)
        base_y = gap + fy * (face_size + gap)
        grid = cube.get_face(face)
        for r in range(3):
            for c in range(3):
                color_name = grid[r][c].name
                rgb = COLORS.get(color_name, (128, 128, 128))
                x1 = base_x + border + c * (cell_size + border)
                y1 = base_y + border + r * (cell_size + border)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                draw.rectangle([x1, y1, x2, y2], fill=rgb, outline=(20, 20, 20), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


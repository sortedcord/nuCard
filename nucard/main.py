import os
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, DataTable, Label, Button, Input, DirectoryTree, TextArea, Static
from textual.containers import Horizontal, Grid
from rich.text import Text
from textual.screen import ModalScreen
from pathlib import Path
from textual.coordinate import Coordinate
from utils import is_audio_file, iterdir, match_property, parse_duration
import base64
import mutagen
import io
from rich_pixels import Pixels
from PIL import Image
from mutagen.flac import Picture, FLACNoHeaderError


class FilePickerScreen(ModalScreen[str]):
    """Screen to choose file/dir"""
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Locate the file or folder"),
            DirectoryTree("/data/Music/Music"),
            Input(),
            Button("Enter", id="submit", variant="primary"),
            Button("Cancel", id="cancel", variant="error"),
            classes="dialog"
        )

    def on_mount(self) -> None:
        tree = self.query_one(DirectoryTree)
        tree.center_scroll = True
        self.query_one(Input).value = str(tree.path)

    def tree_change(self):
        tree = self.query_one(DirectoryTree)
        self.path_line_lookup = {
            str(tree.get_node_at_line(line).data.path): line
            for line in range(0, tree.last_line)
        }
    
    def on_directory_tree_directory_selected(self, event:DirectoryTree.DirectorySelected) -> None:
        self.tree_change()
        path = event.path
        self.query_one(Input).value = str(path)

    def on_directory_tree_file_selected(self, event:DirectoryTree.FileSelected) -> None:
        self.tree_change()
        path = event.path
        self.query_one(Input).value = str(path)
    
    def on_input_changed(self, event:Input.Changed) -> None:
        self.tree_change()
        if os.path.exists(event.value) and not event.value.endswith('/'):
            line = self.path_line_lookup[event.value]
            (tree := self.query_one(DirectoryTree)).cursor_line = line
            tree.scroll_to_line(line)
            tree.get_node_at_line(line).expand()

    def on_button_pressed(self, event:Button.Pressed) -> None:
        if event.button.id == "submit":
            text_area:Input = self.query_one(Input)

            if Path(text_area.value).is_dir():
                paths = iterdir(text_area.value)
                self.dismiss(filter(is_audio_file, paths))
            if is_audio_file(text_area.value):
                self.dismiss([text_area.value])
            else: 
                self.app.notify("Selected file is not an audio file.")
        else:
            self.dismiss("")


class File():
    def __init__(self, path:Path) -> None:
        self.path:Path = path
        self.muta_ob = mutagen.File(path)
        self.image = None
        self.changed = False
        self.properties = dict(self.muta_ob)        

        pic = None
        raw_data = None
        if hasattr(self.muta_ob, "pictures"):
            pic = self.muta_ob.pictures[0]
        elif "metadata_block_picture" in self.properties:
            raw_data = self.properties["metadata_block_picture"][0]

        if raw_data:
            image_bytes = base64.b64decode(raw_data.encode('utf-8'))
            try:
                pic = Picture(image_bytes)
            except FLACNoHeaderError:
                raise
        
        if pic:
            image_stream = io.BytesIO(pic.data)
            image = Image.open(image_stream)
            img_resized = image.resize((38, 27))
            self.image = Pixels.from_image(img_resized)
            # Open image from raw image data in PIL

        delete_tags = [
            "metadata_block_picture",
            "covr"
        ]

        for tag in delete_tags:
            if tag in self.properties:
                del self.properties[tag]
        
        # Get duration using mutagen
        self.duration:str = parse_duration(self.muta_ob.info.pprint().split(",")[1])
        
        self.convert_aac_tags()

    def get_property(self, property:str) -> str:
        if property in self.properties.keys():
            return self.properties[property]
        return "Not defined"

    def convert_aac_tags(self) -> None:
        """
        Convert AAC tags to standard tags.
        """
        if str(self.path).endswith(".m4a") or str(self.path).endswith(".aac"):
            convert_dict = {
                '----:com.apple.iTunes:REPLAYGAIN_ALBUM_GAIN': 'REPLAYGAIN_ALBUM_GAIN',
                '----:com.apple.iTunes:REPLAYGAIN_ALBUM_PEAK': 'REPLAYGAIN_ALBUM_PEAK',
                '----:com.apple.iTunes:REPLAYGAIN_TRACK_GAIN': 'REPLAYGAIN_TRACK_GAIN',
                '----:com.apple.iTunes:REPLAYGAIN_TRACK_PEAK': 'REPLAYGAIN_TRACK_PEAK',
                'aART': 'albumartist',
                'disk': 'discnumber',
                'trkn': 'tracknumber',
                '©ART': 'artist',
                '©alb': 'album',
                '©cmt': 'comment',
                '©day': 'date',
                '©nam': 'title',
                '©too': 'encoder'
            }

            new_properties:dict = {}

            for key, val in self.properties.items():
                if key in convert_dict:
                    new_key = convert_dict[key]
                    if new_key not in new_properties:
                        new_properties[new_key] = []
                    if isinstance(val, list):
                        for v in val:
                            new_properties[new_key].append(v)
                    else:
                        new_properties[new_key].append(val)
                else:
                    new_properties[key] = val
            self.properties = new_properties


class Property_Editor(TextArea):
    BINDINGS = [
            Binding("escape", "enter_value", "Submit", show=True),
        Binding("Ctrl+u", "reset_value", "Reset Value", show=True),
            Binding("Ctrl+r", "delete_value", "Delete", show=True),
        ]
    
    def __init__(self, text:str, key:str):
        super().__init__(text=text)
        self.id = "property_editor"
        self.key = key

    def action_enter_value(self):
        _input = Input(placeholder="Search Property", id="property_search_input")
        self.app.query_one("#edit_bar").mount(_input)
        self.app.query_one(Property_list).update(self.key, self.text)
        self.app.query_one("#property_search_input", Input).focus()
        self.remove()


class Property_list(DataTable):
    BINDINGS = [
        Binding("w", "save_file", "Save File"),
        Binding("/", "search_property", "Search Property")
    ]
    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.classes = "datatable"
        self.add_columns("Property", "Old Value", "New Value")
        self.current_property = None

    def action_search_property(self):
        try:
            self.app.query_one("#property_search_input", Input).focus()
        except:
            raise
    
    def load_file(self, file:File) -> None:
        self.clear()
        for key, val in file.properties.items():
            if len(val) == 1:
                val = val[0]
            else:
                val = "\n".join(val)
            self.add_row(key, val, val, height=None, key=key)
        self.app.CURRENT_FILE = file
        if file.image:
            self.app.query_one("#cover_image", Static).update(file.image)
    
    def update(self, key, value):
        row_index = self.get_row_index(key)
        self.update_cell_at(Coordinate(row=row_index, column=2), value=value, update_width=True)
        if value != self.app.CURRENT_FILE.get_property(key):
            self.set_row_as_changed(row_index)
    
    def set_row_as_changed(self, row_index:int):
        row_vals = self.get_row_at(row_index)
        for i in range(0,3):
            self.update_cell_at(Coordinate(row=row_index, column=i), 
                                value=Text(row_vals[i], style="italic #e3dc0e"))




class File_list(DataTable):

    BINDINGS = [
    Binding("enter", "select_cursor", "Select", show=False),
    Binding("k", "cursor_up", "Cursor up", show=False),
    Binding("j", "cursor_down", "Cursor down", show=False),
    # Binding("gg", "scroll_home", "Home", show=False),
    # Binding("end", "scroll_end", "End", show=False),
]

    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.classes = "datatable"
        self.add_columns(*("Track", "Title", "Artist", "Album", "Duration"))
    
    def push_file(self, file:File):
        self.add_row(file.get_property('tracknumber')[0],
                     file.get_property('title')[0],
                     ",".join(file.get_property('artist')),
                     file.get_property('album')[0],
                     file.duration, key=str(file.path))


class MusicManagerApp(App):
    """A Textual app to manage stopwatches."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
                ("o", "add_files", "Add Files"),
                Binding("escape", "escape_focus", "Escape Focus", show=False)]
    
    CSS_PATH = "styles/main.tcss"

    OPEN_FILES:list[File] = []
    CURRENT_FILE:File|None = None


    def get_file_from_path(self, path:str) -> File|None:
        for file in self.OPEN_FILES:
            if str(file.path) == path:
                return file
        return None

    def open_files(self, file:File) -> None:
        """
        Called when OPEN_FILES changes
        """
        if file not in self.OPEN_FILES:
            self.OPEN_FILES.append(file)
            self.query_one(File_list).push_file(file)


    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Grid(
            Header(),
            Horizontal(
                File_list(),
                Static(id="cover_image"),
            ),
            Horizontal(
                Label("Property Name", id="property_label"),
                Input(placeholder="Search Property", id="property_search_input"),
                id="edit_bar"                 
            ),
            Property_list(),
            Footer(),

            id="appgrid"
        )
    
    def on_input_changed(self, event:Input.Changed):
        property_table = self.query_one(Property_list)
        if event.input.id == "property_search_input":
            prop =  event.input.value
            if self.CURRENT_FILE is None:
                return
            properties = self.CURRENT_FILE.properties.keys()
            key = match_property(prop, properties)

            if key:
                row = property_table.get_row_index(key)
                property_table.move_cursor(row=row)

    def on_input_submitted(self, event:Input.Submitted):
        property_table = self.query_one(Property_list)
        if event.input.id == "property_search_input":
            if self.CURRENT_FILE is None:
                return
            if event.input.value == "":
                return
            selected_row = property_table.get_row_at(property_table.cursor_row)
            textarea = Property_Editor(text=selected_row[-1], key=property_table.current_property)
            self.query_one("#edit_bar").mount(textarea, after=self.query_one("#property_search_input"))
            event.input.remove()
    

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
    
    def on_data_table_row_highlighted(self, event:DataTable.RowHighlighted):
        if isinstance(event.data_table, Property_list):
            event.data_table.current_property = event.row_key.value
            self.query_one("#property_label", Label).update(event.row_key.value)

        file = self.get_file_from_path(str(event.row_key.value))
        if file is None:
            return
        self.query_one(Property_list).load_file(file)

    def action_add_files(self) -> None:
        """
        An Action to add files to MMA
        """
        def get_path(paths: list | None) -> None:
            if paths:
                for path in paths:
                    self.open_files(File(Path(path)))
        self.push_screen(FilePickerScreen(), get_path)
    
    def on_mount(self):
        if args.path:
            if os.path.isdir(args.path):
                paths = iterdir(args.path)
                audio_files = filter(is_audio_file, paths)
                for path in audio_files:
                    self.open_files(File(Path(path)))
            elif is_audio_file(args.path):
                self.open_files(File(args.path))

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Music Manager App")
    parser.add_argument("path", type=str, help="Path to the music file or directory")
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    
    app = MusicManagerApp()
    app.run()
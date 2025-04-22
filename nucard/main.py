import os
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, DataTable, Label, Button, Input, DirectoryTree
from textual.containers import Vertical, Horizontal, VerticalScroll, Container, Grid
from textual.screen import ModalScreen
from pathlib import Path
from textual.reactive import reactive
from utils import is_audio_file
import mutagen


class File():
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

            new_properties = {}

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
    
    def __init__(self, path:Path) -> None:
        self.path:Path = path

        self.properties:dict = mutagen.File(path)

        delete_tags = [
            "metadata_block_picture",
            "covr"
        ]

        for tag in delete_tags:
            if tag in self.properties:
                del self.properties[tag]
        
        self.convert_aac_tags()
        
    



class Property_list(DataTable):
    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.classes = "datatable"
        self.add_columns("Property", "Old Value", "New Value")
    
    def load_file(self, file:File) -> None:
        self.clear()
        for key, val in file.properties.items():
            if len(val) == 1:
                val = val[0]
            else:
                val = ";".join(val)
            self.add_row(key, val, val)

class File_list(DataTable):

    BINDINGS = [
    Binding("enter", "select_cursor", "Select", show=False),
    Binding("k", "cursor_up", "Cursor up", show=False),
    Binding(
        "j", "cursor_down", "Cursor down", show=False
    ),
    Binding("gg", "scroll_home", "Home", show=False),
    # Binding("end", "scroll_end", "End", show=False),
]


    def __init__(self):
        super().__init__()
        self.cursor_type = "row"
        self.classes = "datatable"
        self.add_columns(*("Track no.", "Title", "Artist", "Album", "Duration"))
    
    def push_file(self, file:File):
        self.add_row(file.properties['tracknumber'][0],
                     file.properties['title'][0],
                     ",".join(file.properties['artist']),
                     file.properties['album'][0],
                     "0", key=str(file.path))

class FilePickerScreen(ModalScreen[str]):
    """Screen to choose file/dir"""
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Locate the file or folder"),
            DirectoryTree("/data/Music/Music"),
            Input(),
            Grid(Button("Enter", id="submit"),
            Button("Cancel", id="cancel"))
        )

    def on_mount(self) -> None:
        tree = self.query_one(DirectoryTree)
        tree.center_scroll = True
        self.query_one(Input).value = str(tree.path)

    def tree_change(self):
        tree:DirectoryTree = self.query_one(DirectoryTree)
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
            if is_audio_file(text_area.value):
                self.dismiss(text_area.value)
        else:
            self.dismiss(False)

class MusicManagerApp(App):
    """A Textual app to manage stopwatches."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
                ("o", "add_files", "Add Files")]
    
    CSS_PATH = "styles/main.tcss"

    OPEN_FILES = []

    def get_file_from_path(self, path:str) -> File:
        for file in self.OPEN_FILES:
            if str(file.path) == path:
                return file

    def open_files(self, file:File) -> None:
        """
        Called when OPEN_FILES changes
        """
        self.OPEN_FILES.append(file)
        self.query_one(File_list).push_file(file)


    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()

        yield    File_list()
        yield    Horizontal(
                Label("Property Name"),
                Input(placeholder="Property Value set"),
                id="edit_bar"
            )
        yield    Property_list()        
        
        yield Footer()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
    
    def on_data_table_row_highlighted(self, event:DataTable.RowHighlighted):
        if event.data_table.id != "file_list":
            return

        file = self.get_file_from_path(event.row_key)
        self.query_one(Property_list).load_file(file)

    def action_add_files(self) -> None:
        """
        An Action to add files to MMA
        """
        def get_path(path: str | None) -> None:
            if path:
                self.open_files(File(Path(path)))
        self.push_screen(FilePickerScreen(), get_path) 


if __name__ == "__main__":
    app = MusicManagerApp()
    app.run()
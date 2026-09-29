import io
from PIL import Image
import pytest
from studio.classroom.samples import SampleLibrary


def image(path, colour='blue'):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (800, 400), colour).save(path)


def test_library_only_exposes_images_for_the_selected_class(tmp_path):
    image(tmp_path / 'Color Artwork' / 'colour.jpg')
    image(tmp_path / 'B&W Sketch' / 'sketch.png')
    (tmp_path / 'B&W Sketch' / 'notes.md').write_text('not an image')
    library = SampleLibrary(tmp_path)
    colour, sketch = library.files('colour'), library.files('sketch')
    assert len(colour) == len(sketch) == 1
    assert not set(colour) & set(sketch)
    with pytest.raises(KeyError):
        library.image('sketch', next(iter(colour)))
    with pytest.raises(KeyError):
        library.image('colour', '../../outside')
    data = library.image('colour', next(iter(colour)), thumbnail=True)
    with Image.open(io.BytesIO(data)) as thumbnail:
        assert thumbnail.size == (320, 160)
        assert thumbnail.format == 'JPEG'


def test_library_refuses_links_outside_its_directory(tmp_path):
    image(tmp_path / 'outside.jpg')
    folder = tmp_path / 'Color Artwork'; folder.mkdir()
    (folder / 'linked.jpg').symlink_to(tmp_path / 'outside.jpg')
    assert SampleLibrary(tmp_path).files('colour') == {}
    assert SampleLibrary(tmp_path).files('sketch') == {}

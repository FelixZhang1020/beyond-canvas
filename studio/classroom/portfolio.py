"""Local course portfolios. No credentials or child identity profiles, and one recording a drawing at most.

That recording is the first answer a child said out loud about the drawing, kept so the
drawing's page of a storybook can be read in that child's voice (studio/voice/child_voice.py). It is stored against
that answer and goes when the answer goes.

SQLite transactions keep course metadata, artwork and completed results together.
Connections are short lived so HTTP/worker threads and restarts share durable data.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import sqlite3

from PIL import Image, ImageOps


class CourseClosed(ValueError):
    """An explicit course completion blocks every content write."""


class DrawingInUse(ValueError):
    """A drawing that cannot be deleted yet, with the reason the page shows for it."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def now():
    return datetime.now(timezone.utc).isoformat()


def title_for(entrance, language):
    names = {"zh": {"colour": "彩画课堂", "sketch": "素描课堂"},
             "en": {"colour": "Colour class", "sketch": "Sketch class"}}
    return names[language][entrance] + " · " + datetime.now().strftime("%m.%d")


class Portfolio:
    # A drawing never changes once it is saved, so the small copy made for the
    # home screen is made once. It used to be built afresh on every request --
    # a 2.5 MB photograph decoded, shrunk and re-encoded, about 70 ms each, six
    # tiles a visit, 232 times in one day alone. Keyed by when the drawing
    # was saved, so a replaced one is never served from here.
    THUMBNAILS_HELD = 240

    def __init__(self, path):
        self.path = Path(path)
        self._thumbnails = {}
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, entrance TEXT NOT NULL,
                    language TEXT NOT NULL, lesson_intent TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS course_drafts (
                    course_id TEXT PRIMARY KEY REFERENCES courses(id), content TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artwork (
                    id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses(id),
                    image BLOB NOT NULL, mime TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS artwork_course ON artwork(course_id);
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses(id),
                    skill TEXT NOT NULL, drawings TEXT NOT NULL, summary TEXT NOT NULL,
                    output TEXT NOT NULL, created_at TEXT NOT NULL, ending TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS activities_course ON activities(course_id);
                CREATE TABLE IF NOT EXISTS voices (
                    course_id TEXT NOT NULL, drawing_id TEXT NOT NULL,
                    activity_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                    audio BLOB NOT NULL, created_at TEXT NOT NULL, said TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (course_id, drawing_id)
                );
                CREATE TABLE IF NOT EXISTS narrations (
                    course_id TEXT NOT NULL, drawing_id TEXT NOT NULL, text_key TEXT NOT NULL,
                    audio BLOB NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (course_id, drawing_id, text_key),
                    FOREIGN KEY (course_id, drawing_id) REFERENCES voices(course_id, drawing_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS readings (
                    book_id TEXT NOT NULL REFERENCES activities(id) ON DELETE CASCADE, text_key TEXT NOT NULL,
                    audio BLOB NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (book_id, text_key)
                );
            """)
            # The words heard in a kept recording came a day after its table, on the Spark already.
            if "said" not in {row[1] for row in db.execute("PRAGMA table_info(voices)")}:
                db.execute("ALTER TABLE voices ADD COLUMN said TEXT NOT NULL DEFAULT ''")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def begin(self, sid, entrance, language, intent, title=None):
        title = self.valid_title(title or title_for(entrance, language))
        at = now()
        with self.connect() as db:
            db.execute("INSERT INTO courses VALUES (?,?,?,?,?,?,?,NULL)",
                       (sid, title, entrance, language, intent, at, at))

    @staticmethod
    def valid_title(title):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("Course name must contain 1–120 characters.")
        return title.strip()

    @staticmethod
    def _require_open(db, sid):
        row = db.execute("SELECT ended_at FROM courses WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise KeyError("No such course.")
        if row["ended_at"] is not None:
            raise CourseClosed("This course has ended. Reopen it before editing.")

    def require_open(self, sid):
        with self.connect() as db:
            self._require_open(db, sid)

    @contextmanager
    def writable(self, sid):
        # Lock the state check and the write together: completion cannot slip
        # between them, including writes from an already-running model request.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_open(db, sid)
            yield db

    def rename(self, sid, title):
        title = self.valid_title(title)
        with self.writable(sid) as db:
            if not db.execute("UPDATE courses SET title=?, updated_at=? WHERE id=?", (title, now(), sid)).rowcount:
                raise KeyError("No such course.")

    def settings(self, sid, language, intent):
        with self.writable(sid) as db:
            db.execute("UPDATE courses SET language=?, lesson_intent=?, updated_at=? WHERE id=?",
                       (language, intent, now(), sid))

    def end(self, sid):
        with self.connect() as db:
            if not db.execute("UPDATE courses SET ended_at=COALESCE(ended_at,?), updated_at=? WHERE id=?", (now(), now(), sid)).rowcount:
                raise KeyError("No such course.")

    def reopen(self, sid):
        with self.connect() as db:
            if not db.execute("UPDATE courses SET ended_at=NULL, updated_at=? WHERE id=?", (now(), sid)).rowcount:
                raise KeyError("No such course.")

    def add_drawing(self, sid, did, data, mime):
        with self.writable(sid) as db:
            db.execute("INSERT INTO artwork VALUES (?,?,?,?,?)", (did, sid, data, mime, now()))
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))

    def remove_drawing(self, sid, did):
        """Erase one drawing and everything made from it alone, for good.

        A book is made from several children's drawings, so a drawing a book shares is refused
        rather than taking the others' work with it (operator). `secure_delete`
        overwrites the freed pages: a deleted photograph must not stay readable in the file.
        """
        with self.writable(sid) as db:
            db.execute("PRAGMA secure_delete = ON")
            if db.execute("SELECT 1 FROM artwork WHERE course_id=? AND id=?", (sid, did)).fetchone() is None:
                raise KeyError("No such drawing in this course.")
            made = [(row["id"], json.loads(row["drawings"])) for row in
                    db.execute("SELECT id,drawings FROM activities WHERE course_id=?", (sid,))]
            if any(did in drawings and len(drawings) > 1 for _, drawings in made):
                raise DrawingInUse("This drawing is part of a book.", "in_book")
            db.executemany("DELETE FROM activities WHERE id=?", [(aid,) for aid, drawings in made if did in drawings])
            row = db.execute("SELECT content FROM course_drafts WHERE course_id=?", (sid,)).fetchone()
            if row:
                drafts = json.loads(row[0]); drafts.pop(did, None)
                db.execute("UPDATE course_drafts SET content=? WHERE course_id=?",
                           (json.dumps(drafts, ensure_ascii=False), sid))
            db.execute("DELETE FROM artwork WHERE course_id=? AND id=?", (sid, did))
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))
        self._thumbnails.pop((sid, did), None)

    def delete_course(self, sid):
        """Erase a whole course for good: every drawing, everything made from them, the course itself.

        Asked for from Lesson settings, and chosen over a restorable delete: nothing
        is kept to undo it with. An ended course may be deleted too. `secure_delete`, as for one
        drawing: the photographs must not stay readable in the file.
        """
        with self.connect() as db:
            db.execute("PRAGMA secure_delete = ON")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM courses WHERE id=?", (sid,)).fetchone() is None:
                raise KeyError("No such course.")
            for table in ("activities", "course_drafts", "artwork"):
                db.execute(f"DELETE FROM {table} WHERE course_id=?", (sid,))
            db.execute("DELETE FROM courses WHERE id=?", (sid,))
        for key in [key for key in self._thumbnails if key[0] == sid]:
            self._thumbnails.pop(key, None)

    def forget_chat(self, sid, did, last_round=False):
        """Erase one drawing's conversation for good, or only its last round (operator).

        A round is the child's words and everything the companion said after them. The whole
        conversation also takes the opening, so the next look at the drawing starts afresh. The
        drawing and everything else made from it stay. `secure_delete`, as for a drawing: these
        are a child's own words.
        """
        with self.writable(sid) as db:
            db.execute("PRAGMA secure_delete = ON")
            # The order course() reads them in, which is what the page and a reopened class see as the
            # last round; ordering by rowid could disagree when two share a timestamp (review).
            turns = [(row["id"], row["skill"]) for row in db.execute(
                "SELECT id,skill,drawings FROM activities WHERE course_id=? AND skill IN "
                "('confirmed-words','art-feedback') ORDER BY created_at,id", (sid,))
                     if json.loads(row["drawings"]) == [did]]
            if last_round:
                said = [at for at, (_, skill) in enumerate(turns) if skill == "confirmed-words"]
                if not said:
                    raise DrawingInUse("There is no answer to take back.", "nothing_to_undo")
                turns = turns[said[-1]:]
            db.executemany("DELETE FROM activities WHERE id=?", [(aid,) for aid, _ in turns])
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))
        return len(turns)

    def keep_voice(self, sid, did, activity_id, audio, said=""):
        """Keep the recording sent with a child's answer, if it is the first about this drawing.

        Tied to that answer by the table's cascade, and every page read from it to the recording, so every
        way an answer is erased (taking it back, clearing the chat, deleting the drawing or the course, all
        under `secure_delete`) erases them too.
        """
        with self.writable(sid) as db:
            db.execute("INSERT OR IGNORE INTO voices (course_id,drawing_id,activity_id,audio,created_at,said) "
                       "VALUES (?,?,?,?,?,?)", (sid, did, activity_id, audio, now(), said))

    def voice(self, sid, did):
        """The drawing's kept recording as (WAV, the words heard in it or "", when it was kept), or None."""
        with self.connect() as db:
            row = db.execute("SELECT audio,said,created_at FROM voices WHERE course_id=? AND drawing_id=?",
                             (sid, did)).fetchone()
        return (bytes(row["audio"]), row["said"], row["created_at"]) if row else None

    def keep_narration(self, sid, did, key, audio):
        """A page read in the drawing's kept voice (MP3), by its text's key; refused once the recording is gone."""
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO narrations VALUES (?,?,?,?,?)", (sid, did, key, audio, now()))

    def narration(self, sid, did, key):
        with self.connect() as db:
            row = db.execute("SELECT audio FROM narrations WHERE course_id=? AND drawing_id=? AND text_key=?",
                             (sid, did, key)).fetchone()
        return bytes(row["audio"]) if row else None

    _BOOK = "SELECT id FROM activities WHERE course_id=? AND skill='drawings-to-storybook'"

    def keep_reading(self, sid, key, audio):
        """A sentence of the class's book read in the studio's voice (MP3), kept with that book and gone with it
        (studio/voice/book_voice.py); nothing is kept for a class with no book."""
        with self.connect() as db:
            db.execute(f"INSERT OR REPLACE INTO readings SELECT id,?,?,? FROM ({self._BOOK} LIMIT 1)",
                       (key, audio, now(), sid))

    def reading(self, sid, key):
        with self.connect() as db:
            row = db.execute(f"SELECT audio FROM readings WHERE text_key=? AND book_id IN ({self._BOOK})",
                             (key, sid)).fetchone()
        return bytes(row["audio"]) if row else None

    def record(self, sid, activity_id, skill, drawings, output):
        # Large 3D/PNG payloads are loaded only when a result is opened.
        summary = {key: output[key] for key in ("text", "question", "beat", "status", "message", "reason_code", "scene_description", "outline", "scenes") if key in output}
        summary["kind"] = ("book" if "pages" in output else "relight" if "scene" in output
                           else "figure" if "figure" in output
                           else "keyframe" if "keyframe" in output else "video" if "video_url" in output else "text")
        if skill in ("scene-description", "story-outline", "book-pictures"):   # none is a result of its own
            summary["kind"] = "draft"
        with self.writable(sid) as db:
            if skill == "confirmed-words":
                row = db.execute("SELECT content FROM course_drafts WHERE course_id=?", (sid,)).fetchone()
                if row:
                    drafts = json.loads(row[0])
                    for did in drawings:
                        drafts.pop(did, None)
                    db.execute("UPDATE course_drafts SET content=? WHERE course_id=?",
                               (json.dumps(drafts, ensure_ascii=False), sid))
            ending = ""
            if summary["kind"] == "book":
                # A course has one finished book. Replace it only in the same transaction
                # as the new result, so a failed save leaves the previous book intact.
                # Keep a child's confirmed ending when the new pages are identical.
                db.execute("PRAGMA secure_delete = ON")
                old_books = db.execute("SELECT id,output,ending FROM activities WHERE course_id=? AND skill='drawings-to-storybook'",
                                       (sid,)).fetchall()
                pages = [(p.get("drawing_id"), p.get("text")) for p in output["pages"]]
                for old in old_books:
                    prior = json.loads(old["output"]).get("pages", [])
                    if old["ending"] and pages == [(p.get("drawing_id"), p.get("text")) for p in prior]:
                        ending = old["ending"]
                    db.execute("DELETE FROM activities WHERE id=?", (old["id"],))
            db.execute("INSERT INTO activities (id,course_id,skill,drawings,summary,output,created_at) VALUES (?,?,?,?,?,?,?)",
                       (activity_id, sid, skill, json.dumps(drawings), json.dumps(summary, ensure_ascii=False),
                        json.dumps(output, ensure_ascii=False, allow_nan=False), now()))
            if ending:
                db.execute("UPDATE activities SET ending=? WHERE id=?", (ending, activity_id))
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))

    def courses(self, query="", entrance="", offset=0):
        if entrance not in ("", "colour", "sketch") or offset < 0 or len(query) > 200:
            raise ValueError("Invalid course filter.")
        # Treat wildcard characters as literal search text.
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where = "WHERE (title LIKE ? ESCAPE '\\' OR lesson_intent LIKE ? ESCAPE '\\')"
        values = [pattern, pattern]
        if entrance:
            where += " AND entrance=?"; values.append(entrance)
        with self.connect() as db:
            total = db.execute("SELECT count(*) FROM courses " + where, values).fetchone()[0]
            rows = db.execute("""SELECT courses.*,
                (SELECT count(*) FROM artwork WHERE course_id=courses.id) AS drawing_count,
                (SELECT count(*) FROM activities WHERE course_id=courses.id AND skill!='confirmed-words') AS activity_count,
                (SELECT id FROM artwork WHERE course_id=courses.id ORDER BY created_at LIMIT 1) AS cover_id
                FROM courses """ + where + " ORDER BY created_at DESC, id DESC LIMIT 24 OFFSET ?", values + [offset]).fetchall()
        items = [dict(row) for row in rows]
        for item in items:
            cover_id = item.pop("cover_id")
            item["cover_url"] = self.art_url(item["id"], cover_id, True) if cover_id else None
        return {"items": items, "total": total, "next_offset": offset + len(items) if offset + len(items) < total else None}

    @staticmethod
    def art_url(sid, did, thumbnail=False):
        return f"/api/courses/{sid}/drawings/{did}" + ("?thumbnail=1" if thumbnail else "")

    def course(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM courses WHERE id=?", (sid,)).fetchone()
            if row is None:
                raise KeyError("No such course.")
            result = dict(row)
            draft = db.execute("SELECT content FROM course_drafts WHERE course_id=?", (sid,)).fetchone()
            result["drafts"] = json.loads(draft[0]) if draft else {}
            drawings = db.execute("SELECT id,created_at FROM artwork WHERE course_id=? ORDER BY created_at,id", (sid,)).fetchall()
            activities = db.execute("SELECT id,skill,drawings,summary,created_at,ending FROM activities WHERE course_id=? ORDER BY created_at,id", (sid,)).fetchall()
        result["drawings"] = [{**dict(row), "url": self.art_url(sid, row["id"]),
                                "thumbnail_url": self.art_url(sid, row["id"], True)} for row in drawings]
        result["activities"] = [{**dict(row), "drawings": json.loads(row["drawings"]),
                                  "summary": json.loads(row["summary"])} for row in activities]
        return result

    def save_drafts(self, sid, drafts):
        if not isinstance(drafts, dict) or len(drafts) > 100:
            raise ValueError("Expected at most 100 answer drafts.")
        if any(not isinstance(text, str) or len(text) > 10000 for text in drafts.values()):
            raise ValueError("Each answer draft must contain at most 10000 characters.")
        with self.writable(sid) as db:
            ids = {row[0] for row in db.execute("SELECT id FROM artwork WHERE course_id=?", (sid,))}
            if any(did not in ids for did in drafts):
                raise ValueError("Draft drawings must belong to this course.")
            db.execute("INSERT OR REPLACE INTO course_drafts VALUES (?,?)",
                       (sid, json.dumps(drafts, ensure_ascii=False)))

    def drawing(self, sid, did, thumbnail=False):
        if thumbnail:
            # Asked before the picture itself is read: the photograph is megabytes
            # and this answers without touching it when the small copy is already made.
            with self.connect() as db:
                saved = db.execute("SELECT created_at FROM artwork WHERE course_id=? AND id=?",
                                   (sid, did)).fetchone()
            if saved is None:
                raise KeyError("No such drawing in this course.")
            held = self._thumbnails.get((sid, did))
            if held and held[0] == saved["created_at"]:
                return held[1], "image/jpeg"
        with self.connect() as db:
            row = db.execute("SELECT image,mime FROM artwork WHERE course_id=? AND id=?", (sid, did)).fetchone()
        if row is None:
            raise KeyError("No such drawing in this course.")
        if not thumbnail:
            return row["image"], row["mime"]
        with Image.open(io.BytesIO(row["image"])) as source:
            image = ImageOps.exif_transpose(source).convert("RGB"); image.thumbnail((560, 560))
            data = io.BytesIO(); image.save(data, format="JPEG", quality=85)
        small = data.getvalue()
        if len(self._thumbnails) >= self.THUMBNAILS_HELD:
            self._thumbnails.clear()
        self._thumbnails[(sid, did)] = (saved["created_at"], small)
        return small, "image/jpeg"

    def latest_video(self, sid, did):
        """Use the latest saved video for this drawing; never generate while reading."""
        with self.connect() as db:
            rows = db.execute("SELECT drawings,output FROM activities WHERE course_id=? AND skill=? ORDER BY created_at DESC,rowid DESC",
                              (sid, "painting-to-animation"))
            for row in rows:
                if did in json.loads(row["drawings"]):
                    video = json.loads(row["output"]).get("video_url")
                    if video:
                        return video
        return None

    def latest_picture(self, sid, did, style):
        """The newest page of this drawing redrawn in this picture-book style (book-pictures), or None."""
        with self.connect() as db:
            rows = db.execute("SELECT output FROM activities WHERE course_id=? AND skill=? ORDER BY created_at DESC,rowid DESC",
                              (sid, "book-pictures"))
            for row in rows:
                for picture in json.loads(row["output"]).get("pictures", []):
                    if picture.get("drawing_id") == did and picture.get("style") == style and picture.get("url"):
                        return picture
        return None

    def activity(self, sid, aid):
        with self.connect() as db:
            row = db.execute("SELECT output,ending FROM activities WHERE course_id=? AND id=?", (sid, aid)).fetchone()
        if row is None:
            raise KeyError("No such result in this course.")
        return {"outputs": json.loads(row["output"]), "ending": row["ending"], "artifact_id": aid}

    def ending(self, sid, aid, text):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError("Ending must contain 1–2000 characters.")
        with self.writable(sid) as db:
            row = db.execute("SELECT summary FROM activities WHERE course_id=? AND id=?", (sid, aid)).fetchone()
            if row is None:
                raise KeyError("No such storybook in this course.")
            if json.loads(row["summary"])["kind"] != "book":
                raise ValueError("This result is not a storybook.")
            db.execute("UPDATE activities SET ending=? WHERE course_id=? AND id=?", (text.strip(), sid, aid))
            db.execute("DELETE FROM readings WHERE book_id=?", (aid,))   # the old ending's with them; read ahead again
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))

    def view(self, sid, aid, base):
        """The angle a teacher turned a 3D result to, so it opens facing as the drawing does.

        The automatic check shows the drawing's own angle about half the time and gives up otherwise,
        and all three results it had passed in the Portfolio faced wrong
        (docs/measured/view-calibration.md), so the teacher has the last word.
        Only the angle changes: the model, and the check's own record under `check`, are kept. Two angles
        keep the direction she looked from, not a sideways tilt: turned from a checked base whose height is
        not the viewer's resting 75°, the model reopens standing upright, up to ~16° less tilted than she saw.
        """
        if not (isinstance(base, list) and len(base) == 2
                and all(type(n) in (int, float) and math.isfinite(n) for n in base)
                and -180 <= round(base[0]) <= 180 and 1 <= round(base[1]) <= 179):
            raise ValueError("A view is [yaw from -180 to 180, polar from 1 to 179].")
        with self.writable(sid) as db:
            row = db.execute("SELECT output FROM activities WHERE course_id=? AND id=?", (sid, aid)).fetchone()
            if row is None:
                raise KeyError("No such result in this course.")
            output = json.loads(row["output"])
            scene = output.get("scene") if isinstance(output, dict) else None
            if not isinstance(scene, dict):
                raise ValueError("This result is not a 3D model.")
            if scene.get("method") == "cloud-glb":
                old = scene.get("camera_calibration") or {}
                check = old.get("check") if old.get("status") == "teacher" else old
                scene["camera_base"] = [round(base[0]), round(base[1])]
                scene["camera_calibration"] = {"status": "teacher", "check": check}
            elif scene.get("method") in {"geometric-approximation", "single-image-mesh", "parametric-still-life"}:
                if not isinstance(scene.get("camera"), dict) or not 10 <= round(base[1]) <= 80:
                    raise ValueError("This result has no valid camera angle.")
                scene["camera"]["azimuth"] = round(base[0])
                scene["camera"]["elevation"] = round(base[1])
            else:
                raise ValueError("This result is not a 3D model.")
            db.execute("UPDATE activities SET output=? WHERE course_id=? AND id=?", (json.dumps(output, ensure_ascii=False, allow_nan=False), sid, aid))
            db.execute("UPDATE courses SET updated_at=? WHERE id=?", (now(), sid))

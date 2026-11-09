from . import irantalent, jobinja, jobvision

SOURCES = {m.NAME: m for m in (jobinja, jobvision, irantalent)}
LABELS = {"jobinja": "جابینجا", "jobvision": "جاب‌ویژن", "irantalent": "ایران‌تلنت"}
TAGS = {"jobinja": "#جابینجا", "jobvision": "#جاب_ویژن", "irantalent": "#ایران_تلنت"}

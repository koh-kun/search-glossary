"""
The app's version number. This is the ONLY place it is set.

To release a new version:
    1. Change the number below (e.g. "1.0.1" -> "1.0.2").
    2. Commit and push to main.

GitHub then builds Windows, macOS and Linux and publishes them as
release v1.0.2. Testers running an older version are told about it
the next time they launch the app.

Everything else reads the number from here: the window title, the
About box, the macOS bundle (SearchGlossary.spec), and the GitHub
release (.github/workflows/build.yml).

Format: three whole numbers separated by dots, nothing else.
The release workflow refuses to run on anything like "1.0.2-beta".
"""

APP_VERSION = "1.1.0"

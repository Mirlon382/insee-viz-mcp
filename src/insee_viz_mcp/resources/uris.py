"""The two URIs this server publishes besides its tools.

Kept apart from the resources themselves so `tools/__init__.py` can point a tool at the viewer
without importing the module that reads it.
"""

VIEW_URI = "ui://insee-viz/view.html"
GUIDE_URI = "insee://doctrine/figures"

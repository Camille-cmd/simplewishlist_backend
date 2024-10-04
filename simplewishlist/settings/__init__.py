import os

from .base import *  # noqa

if os.environ["DJANGO_ENV"] == "production":
    from .prod import *  # noqa
else:
    from .dev import *  # noqa

"""Every module in this package defines one game. Importing the package registers them."""
import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")

# Runtime hook to fix typing module for Python 3.13 + PyInstaller
import sys

# Patch typing module to include missing attributes from typing_extensions
try:
    import typing
    import typing_extensions
    
    # Add missing attributes from typing_extensions to typing
    for attr in dir(typing_extensions):
        if not attr.startswith('_') and not hasattr(typing, attr):
            setattr(typing, attr, getattr(typing_extensions, attr))
    
    # Ensure Annotated is available
    if not hasattr(typing, 'Annotated'):
        typing.Annotated = typing_extensions.Annotated
        
except Exception as e:
    print(f"Warning: Failed to patch typing module: {e}")

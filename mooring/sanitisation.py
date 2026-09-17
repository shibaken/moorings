"""
Input Sanitisation Utilities
Defence-in-depth mixins using nh3 to prevent Stored XSS.
See `plan-sanitisation.md` for architectural details.
"""
import logging
import nh3
import html
from django.db import models

logger = logging.getLogger(__name__)

def neutralise_html(value):
    """
    Strips all HTML tags and attributes from a string using nh3,
    and un-escapes HTML entities to store natural plain text.
    Fails safely by returning the original value on error.
    """
    if not isinstance(value, str):
        return value
    try:
        # Strict mode: strip all tags and attributes
        cleaned = nh3.clean(value, tags=set(), attributes={}, strip_comments=True)
        return html.unescape(cleaned)
    except Exception as e:
        logger.error(f"Error sanitising HTML: {e}")
        return value

def _sanitise_json_value(value):
    """Recursively sanitise strings inside JSON structures."""
    if isinstance(value, dict):
        # We only sanitise values. Keys should never contain HTML.
        return {k: _sanitise_json_value(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_sanitise_json_value(v) for v in value]
    elif isinstance(value, str):
        return neutralise_html(value)
    else:
        return value

class SanitisationModelMixin:
    """
    Model mixin to auto-sanitise CharField, TextField, and JSONField on save().
    """
    sanitise_exclude_fields = set()

    def save(self, *args, **kwargs):
        for field in self._meta.get_fields():
            if field.name in self.sanitise_exclude_fields:
                continue

            # Ensure we are only touching concrete Django fields
            if isinstance(field, (models.CharField, models.TextField)):
                value = getattr(self, field.name, None)
                if value is not None:
                    setattr(self, field.name, neutralise_html(value))
            elif isinstance(field, models.JSONField):
                value = getattr(self, field.name, None)
                if value is not None:
                    setattr(self, field.name, _sanitise_json_value(value))
                    
        super().save(*args, **kwargs)

class NH3SanitizeSerializerMixin:
    """
    Serializer mixin to auto-sanitise string and JSON inputs at the DRF boundary.
    """
    sanitise_exclude_fields = set()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for key, value in attrs.items():
            if key in self.sanitise_exclude_fields:
                continue
            
            if isinstance(value, str):
                attrs[key] = neutralise_html(value)
            elif isinstance(value, (dict, list, tuple)):
                attrs[key] = _sanitise_json_value(value)
        return attrs

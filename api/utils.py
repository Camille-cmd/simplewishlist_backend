import inspect
import io
from functools import wraps
from typing import Optional

from pydantic import BaseModel, ValidationError, create_model
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response


# DECORATORS
def validate_data(pydantic_model):
    """
    Decorator used to validate data against the target pydantic_model
    When the validation succeed, the validated model is added to the function's kwargs
    When the validation fails, returns a Response with the errors from the pydantic model
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                kwargs["validated_model"] = pydantic_model.model_validate_json(request.body)
                return func(self, request, *args, **kwargs)
            except ValidationError as e:
                return Response(data={"errors": e.errors()}, status=status.HTTP_400_BAD_REQUEST)

        return wrapper

    return decorator

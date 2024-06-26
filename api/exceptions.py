class SimpleWishlistError(Exception):
    """A base class for Simple Wishlist exceptions."""


class SimpleWishlistValidationError(Exception):
    """
    Exception raised on Models validations
        Attributes:
        message -- explanation of the error
        field -- the field on which the validation failed
        model -- the model for which the validation failed
    """

    def __init__(self, message, field=None, model=None):
        self.message = message
        self.field = field
        self.model = model

    def __str__(self):
        return str(self.message)

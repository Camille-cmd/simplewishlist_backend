class SimpleWishlistError(Exception):
    """A base class for Simple Wishlist exceptions."""


class SimpleWishlistValidationError(Exception):
    """
    Exception raised on Models validations
        Attributes:
        message -- explanation of the error
        field -- the field on which the validation failed
        model -- the model for which the validation failed
        code -- stable machine readable code for the error
    """

    def __init__(self, message, field=None, model=None, code=None):
        self.message = message
        self.field = field
        self.model = model
        self.code = code

    def __str__(self):
        return str(self.message)

from api.exceptions import SimpleWishlistValidationError


def error_handler(func):
    def inner_function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except SimpleWishlistValidationError:
            print(f"{func.__name__} wrong data types. enter numeric")

    return inner_function

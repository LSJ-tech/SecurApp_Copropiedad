from django.conf import settings


def marca(_request):
    """Context processor: Django siempre llama con la request, aunque acá no se use."""
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
        "ANDROID_APP_URL": settings.ANDROID_APP_URL,
    }

from django.utils.translation import activate as activate_language

class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            user_language = request.user.profile.language
            activate_language(user_language)
        return self.get_response(request)
from django.http import JsonResponse


def error_response(message, status):
    return JsonResponse({"error": message}, status=status)


def bad_request(request, exception):
    return error_response("Bad request", 400)


def permission_denied(request, exception):
    return error_response("Forbidden", 403)


def not_found(request, exception):
    return error_response("Not found", 404)


def server_error(request):
    return error_response("Internal server error", 500)


def csrf_failure(request, reason=""):
    return error_response("CSRF verification failed. Fetch /api/csrf before posting.", 403)

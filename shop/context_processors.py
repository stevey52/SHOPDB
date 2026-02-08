def user_roles(request):
    if not request.user.is_authenticated:
        return {'is_manager': False}
    
    is_manager = request.user.is_superuser or request.user.groups.filter(name='Manager').exists()
    return {'is_manager': is_manager}

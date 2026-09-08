from .models import Membership


def workspace(request):
    if request.user.is_authenticated:
        member = Membership.objects.select_related("company").filter(user=request.user).first()
        if member:
            return {"workspace": member.company, "membership": member, "can_edit": member.role in ("admin", "analyst"), "can_manage": member.role == "admin"}
    return {}

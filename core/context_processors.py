from .models import Account


def account_context(request):
    account_id = request.session.get('account_id')
    account = Account.objects.filter(pk=account_id).first() if account_id else None
    display_name = ''
    if account:
        display_name = account.name.strip() or account.email.split('@', 1)[0].replace('.', ' ').replace('_', ' ')
    return {
        'current_account': account,
        'current_account_name': display_name,
        'current_account_initial': display_name[:1].upper(),
    }
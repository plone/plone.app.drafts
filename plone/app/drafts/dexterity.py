
from zope.component import queryUtility

from plone.app.drafts.interfaces import IDraftStorage
from plone.app.drafts.interfaces import ICurrentDraftManagement

from plone.app.drafts.utils import getDefaultKey
from plone.app.drafts.utils import syncDraft
from plone.app.drafts.utils import getCurrentDraft

from Acquisition import aq_parent
from Products.CMFCore.utils import getToolByName


# Helper methods
def getDexterityObjectKey(context, form):
    """Get a key for an Dexterity object. This will be a string
    representation of its intid, unless it is in the dotted form name, in
    which case it'll be the a string like
    "${parent_intid}:portal_factory/${dotted.form.name}"
    """

    # Grab the dotted form name otherwise we can't locate drafts for both a
    # container+edit and an item+add on the same content item
    # (remove dots since its going in the cookie)
    name = ''.join(form.__module__.split('.'))

    portal_factory = getToolByName(context, 'portal_factory', None)
    if portal_factory is None or not portal_factory.isTemporary(context):
        defaultKey = getDefaultKey(context)
        if defaultKey is None:
            # probably the portal root
            defaultKey = '0'
        return "%s:%s" % (defaultKey, name,)

    tempFolder = aq_parent(context)
    folder = aq_parent(aq_parent(tempFolder))

    defaultKey = getDefaultKey(folder)
    if defaultKey is None:
        # probably the portal root
        defaultKey = '0'

    return "%s:%s:%s" % (defaultKey, tempFolder.getId(), name,)


def beginDrafting(context, form):
    """When we enter the edit screen, set up the target key and draft cookie
    path. If there is exactly one draft for the given user id and target key,
    consider that to be the current draft. Also mark the request with
    IDrafting if applicable.
    """
    request = form.request

    if request is None:
        return

    storage = queryUtility(IDraftStorage)
    if storage is None or not storage.enabled:
        return

    current = ICurrentDraftManagement(request)

    # Update target key regardless - we could have a stale cookie
    current.targetKey = getDexterityObjectKey(context, form)

    if current.userId is None:
        # XXX: Remove; was to create a draft before authorized (in adapter
        # __init__.  There should be no need to do this anymore
        #
        # More than likely user has not yet been validated, so try to figure
        # it out (++widgets++ traversal)
        try:
            plone_site = context.unrestrictedTraverse('/' + context.getPhysicalPath()[1])
            plone_pluggable_auth_service = plone_site.__allow_groups__
            plugins = plone_site.__allow_groups__._getOb('plugins')
            user_ids = plone_pluggable_auth_service._extractUserIds(request, plugins)
        except:
            return

        if len(user_ids) == 0:
            root = context.unrestrictedTraverse('/')
            root_pluggable_auth_service = root.__allow_groups__
            plugins = root.__allow_groups__._getOb('plugins')
            user_ids = root_pluggable_auth_service._extractUserIds(request, plugins)

        if len(user_ids) == 0:
            return

        user_id, login = user_ids[0]
        current.userId = user_id

    if current.userId is None:
        return

    if current.draftName is None:
        drafts = storage.getDrafts(current.userId, current.targetKey)
        if len(drafts) == 1:
            current.draftName = tuple(drafts.keys())[0]

    # Save the path now so that we can use it again later, even on URLs
    # (e.g. in AJAX dialogues) that are below this path.
    current.path = current.defaultPath

    # Mark context with IDraft
    current.mark()

    # Set up cookies
    current.save()

    return current


def syncDraftOnSave(context, event):
    """When the edit form is saved, sync the draft (if set) and discard it.
    Also discard the drafting cookies.
    """

    storage = queryUtility(IDraftStorage)
    if storage is None or not storage.enabled:
        return

    request = getattr(context, 'REQUEST', None)
    if request is None:
        return

    draft = getCurrentDraft(request)
    if draft is not None:
        syncDraft(draft, context)

    current = ICurrentDraftManagement(request)
    if current.userId and current.targetKey:
        storage.discardDrafts(current.userId, current.targetKey)

    current.discard()


def discardDraftsOnCancel(context, event):
    """When the edit form is cancelled, discard any unused drafts and
    remove the drafting cookies.
    """

    storage = queryUtility(IDraftStorage)
    if storage is None or not storage.enabled:
        return

    request = getattr(context, 'REQUEST', None)
    if request is None:
        return

    current = ICurrentDraftManagement(request)

    if current.userId and current.targetKey:
        storage.discardDrafts(current.userId, current.targetKey)

    current.discard()

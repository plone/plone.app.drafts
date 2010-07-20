import zope.component
from zope.interface import alsoProvides

from Acquisition.interfaces import IAcquirer
from Acquisition import aq_inner

from plone.app.drafts.utils import syncDraft
from plone.app.drafts.utils import getCurrentDraft
 
from plone.dexterity.interfaces import IDexterityContainer, IDexterityItem
from plone.dexterity.interfaces import IDexterityFTI
from plone.dexterity.utils import createContent

from plone.app.drafts.interfaces import IDexterityDraft
from plone.app.drafts.interfaces import IDexterityDraftAdding
from plone.app.drafts.interfaces import IDexterityDraftEditing

# TODO this should not be here; should be in behaviors
from plone.app.dexterity.behaviors.drafts import IDexterityDraftSubmitBehavior
from plone.app.dexterity.behaviors.drafts import IDexterityDraftCancelBehavior

from plone.app.drafts.interfaces import IDexterityDraftContainer
from plone.app.drafts.interfaces import IDexterityDraftItem
#from experimental.dexterityz3cformdrafts.drafts import setupDraft

################################################################################

from zope.component import queryUtility

from plone.app.drafts.interfaces import IDraftStorage
from plone.app.drafts.interfaces import ICurrentDraftManagement

from plone.app.drafts.utils import syncDraft
from plone.app.drafts.utils import getCurrentDraft
from plone.app.drafts.utils import getDefaultKey

from Acquisition import aq_parent
from Products.CMFCore.utils import getToolByName

# Helper methods

# TODO:  Get rid of archtype specific stuff here
def getDexterityObjectKey(context):
    """Get a key for an Dexterity object. This will be a string
    representation of its intid, unless it is in the portal_factory, in
    which case it'll be the a string like
    "${parent_intid}:portal_factory/${portal_type}"
    """
    
    portal_factory = getToolByName(context, 'portal_factory', None)
    if portal_factory is None or not portal_factory.isTemporary(context):
        return getDefaultKey(context)
    
    tempFolder = aq_parent(context)
    folder = aq_parent(aq_parent(tempFolder))
    
    defaultKey = getDefaultKey(folder)
    if defaultKey is None:
        # probably the portal root
        defaultKey = '0'
    
    return "%s:%s" % (defaultKey, tempFolder.getId(),)

# Main event handlers

##def beginDrafting(context, event):
##    """When we enter the edit screen, set up the target key and draft cookie
##    path. If there is exactly one draft for the given user id and target key,
##    consider that to be the current draft. Also mark the request with
##    IDrafting if applicable.
##    """
##    
##    storage = queryUtility(IDraftStorage)
##    if storage is None or not storage.enabled:
##        return
##    
##    request = getattr(context, 'REQUEST', None)
##    if request is None:
##        return
##    
##    current = ICurrentDraftManagement(request)
##    
##    # Update target key regardless - we could have a stale cookie
##    current.targetKey = getDexterityObjectKey(context)
##    
##    if current.draftName is None:
##        drafts = storage.getDrafts(current.userId, current.targetKey)
##        if len(drafts) == 1:
##            current.draftName = tuple(drafts.keys())[0]
##    
##    # Save the path now so that we can use it again later, even on URLs 
##    # (e.g. in AJAX dialogues) that are below this path.
##    current.path = current.defaultPath
##    
##    current.mark()
##    current.save()
    
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
    
################################################################################

# NOT YET USED
class DexterityDraftError( Exception ):
    """
    """
    pass

def addBegun(form, event):
    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return

##    form.context = getDraftContext( form.context, form.request, form.portal_type, view_name='add' )
##    
##    if IDexterityDraft.providedBy(form.context):
##        form.ignoreContext = False
        
    draftRequestForm(form, event)

def editBegun(form, event):
    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return
    
##    form.context = getDraftContext( form.context, form.request, form.portal_type, view_name='edit' )
    
    draftRequestForm(form, event)

################################################################################

def getDraftContext(context, request, portal_type, view_name=None):
    """Returns a dexterity draft object if the behavior IDexterityDraftable is
       set; otherwise will return original context.  If a draft does not already
       exist, one will be created"""
    
    fti = zope.component.queryUtility( IDexterityFTI, name=portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return context
        
    context = aq_inner( context ) # New
    setupDraft( context, request, portal_type )
    
    #request = getattr(context, 'REQUEST', None)
    if request is None:
        return context
    
    draft = getCurrentDraft(request)
    if draft is None:
        # Don't allow a draft to be created if view_name is None
        # It should be 'add' or 'edit'
        if view_name is None:
            return context

        new_context = createDraftContext( context, portal_type, view_name )
        if new_context is None:
            return context
    else:
        new_context = getattr( draft, 'context', None )
        
    if new_context is None:
        return context

    if IAcquirer.providedBy(new_context):
        new_context = new_context.__of__( context )
    
    return new_context

def createDraftContext(context, portal_type, view_name):
    context = aq_inner(context) #NEW
    request = getattr(context, 'REQUEST', None)
    if request is None:
        return None
    
    draft = getCurrentDraft(request, create=True)
    if draft is None:
        return None
    
    new_context = createContent( portal_type )
    
    alsoProvides( new_context, IDexterityDraft )
    alsoProvides( new_context, IDexterityDraftSubmitBehavior )
    alsoProvides( new_context, IDexterityDraftCancelBehavior )
    
    if IDexterityContainer.providedBy( new_context ):
        alsoProvides( new_context, IDexterityDraftContainer )
    elif IDexterityItem.providedBy( new_context ):
        alsoProvides( new_context, IDexterityDraftItem )

    if view_name == 'add':
        alsoProvides( new_context, IDexterityDraftAdding )
    elif view_name == 'edit':
        alsoProvides( new_context, IDexterityDraftEditing )
        
    new_context.id = '++%s_draft++%s' % (view_name, portal_type)
    new_context.__parent__ = aq_inner( context )
    setattr( draft, 'context', new_context )
    
    if IDexterityDraftEditing.providedBy( new_context ):
        # sync the draft up via data from original context
        syncDraft(context, new_context)
    
    return new_context

################################################################################

def draftRequestForm(form, event):

    fti = zope.component.queryUtility( IDexterityFTI, name=form.portal_type )
    if not 'plone.app.drafts.interfaces.IDexterityDraftable' in fti.behaviors:
        return context
        
    #request = getattr(form.context, 'REQUEST', None)
    #if request is None:
    #    return
    request = form.request
    alsoProvides( request, IDexterityDraft )
    
    content = form.getContent()
    
    #
    # TODO:  Consider a better way of adding behaviors to form.  Problem is
    #        we can't get it from ++add++ form since object has not yet been
    #        created. 
    #        Maybe create a utility for dexterity that could automatically
    #        mark a form; or request -- makes things a wee messy :(
    #
    from z3c.form.interfaces import IAddForm
    if IAddForm.providedBy( form ):
        alsoProvides( form, IDexterityDraftSubmitBehavior )
        alsoProvides( form, IDexterityDraftCancelBehavior )
        
        from plone.app.dexterity.behaviors.drafts import IDexterityDraftSaveBehavior
        if 'plone.app.dexterity.behaviors.drafts.IDexterityDraftSaveBehavior' in fti.behaviors:
            alsoProvides( form, IDexterityDraftSaveBehavior )
 
    setupDraft( content, request, form.portal_type )
    
    draft = getCurrentDraft(request, create=True)
    if draft is None:
        return
    
    from zope.schema import getFields
    from ZPublisher.HTTPRequest import FileUpload
    from z3c.form import interfaces
    
    #draft_request_form = getattr( draft, '_form', {} ).copy()
    #
    # TODO:  save request as attrs not in a dict on draft for compatibility
    #        with other processes using draft for something different?
    #
    draft_request_form = getattr( draft, '_form', {} )
    new_request_form = {}
    button_actions = {}
    fields = getFields( fti.lookupSchema() )
    
    #
    # Edit form must use ignoreContext = True so values are loaded from
    # request; or change named image to grab from request first; if exists?
    # (will need to populate draft with object data initially)
    if request.form.has_key('-C') and len(draft_request_form) == 0:
        if not interfaces.IEditForm.providedBy( form ):
            # Nothing to do 
            return
        # Populate request from content object (initial load)
        if len( draft_request_form ) == 0:
            schema = getFields( fti.lookupSchema() )
            
            for field_name, field_schema in schema.items():
                attr = getattr( content, field_name, NotFound )
                if attr is not NotFound:
                    draft_request_form[field_name] = attr 

            for key, value in draft_request_form.items():
                new_request_form[key] = value
    # Populate request from draft if its empty
    # (should be handled below now)
    #elif request.form.has_key('-C') and len(draft_request_form) != 0:
    #    for key, value in draft_request_form.items():
    #        new_request_form[key] = value
    else:    
        for key, value in request.form.items():
            # Don't save button actions (or recursion can happen)
            if key.startswith( 'form.buttons' ):
                button_actions[key] = value
                continue
            
            # Don't save empty form indicator
            if key == '-C':
                continue
            
            # Save the converted value in draft object since some may be 
            # instancemethod objects (FileUpload is ) which can not be pickled
            field = fields.get(key[key.rfind('.')+1:], None)
            if field is not None:
                # INamed Hack...
                # Need to handle INamed fields special since we can not
                # store the FileUpload object directly because it is
                # an instancemethod
                from plone.namedfile.interfaces import INamedField
                from types import InstanceType
                if INamedField.providedBy( field ):
                    # More than likely ajax inline validation sent a string
                    # containing either the filename or ''
                    if not isinstance(value, FileUpload):
                        value = draft_request_form.get(key, None)
                        if value is None:
                            continue
                    else:
                        widget = zope.component.getMultiAdapter( (field, request), interfaces.IFieldWidget )            
                        converted_value = interfaces.IDataConverter(widget).toFieldValue( value )
                        
                        # Reload image from draft if it exists
                        if converted_value is None: 
                            converted_value = draft_request_form.get(key, None)
                            #if converted_value is not None:
                            if converted_value is None:
                                continue
                            
                        value = converted_value #This may be enough to update request.form?
                        
                # Can not save instancemethods, so skip it (dunno where this
                # could happen other than INamed objects (handled above)
                elif type(value) == InstanceType:
                    continue
                
            new_request_form[key] = value
            
            #DEBUG; test only to see if this will work for preview
            # (set attribute directly; not just on form)
            # if this works; dont set anything not in schema
            #setattr( draft, key[13:], value )
            
    # Draft may still have some stored fields not in request; so get them
    # (only copy over schema fields though) -- needed for ajax updated forms
    for key, value in draft_request_form.items():
        if not request.form.has_key(key) and fields.has_key(key[key.rfind('.')+1:]):
            new_request_form[key] = value
        
    # Re-wrtie the form from draft incase anything was changed since last request
    setattr( draft, '_form', new_request_form.copy() )
    request.form = new_request_form
    
    # Add back in any button actions that were removed to request
    for key, value in button_actions.items():
        request.form[key] = value
    
    return

################################################################################

from zope.component import queryUtility

from plone.app.drafts.interfaces import IDraftStorage
from plone.app.drafts.interfaces import ICurrentDraftManagement

# Helper methods
def setupDraft(context, request=None, portal_type=None):
    """When we enter the edit screen, set up the target key and draft cookie
    path. If there is exactly one draft for the given user id and target key,
    consider that to be the current draft. Also mark the request with
    IDrafting if applicable.
    """
    if request is None:
        return None
    
    storage = queryUtility(IDraftStorage)
    if storage is None or not storage.enabled:
        return None
    
    current = ICurrentDraftManagement(request)
    
    # Update target key regardless - we could have a stale cookie
    current.targetKey = getDexterityObjectKey(context)
    if portal_type is not None:
        current.targetKey += ':' + portal_type
    
    if current.userId is None:
        # More than likely user has not yet been validated, so try to figure 
        # it out
        plone_site = context.unrestrictedTraverse( '/'+context.getPhysicalPath()[1] )
        plone_pluggable_auth_service = plone_site.__allow_groups__
        plugins = plone_site.__allow_groups__._getOb('plugins')
        user_ids = plone_pluggable_auth_service._extractUserIds( request, plugins )

        if len(user_ids) == 0:
            root = context.unrestrictedTraverse('/')
            root_pluggable_auth_service = root.__allow_groups__
            plugins = root.__allow_groups__._getOb('plugins')
            user_ids = root_pluggable_auth_service._extractUserIds( request, plugins )
        
        if len(user_ids) == 0:
            return None

        user_id, login = user_ids[0]
        current.userId = user_id
        
    if current.userId is None:
        return None
        
    if current.draftName is None:
        drafts = storage.getDrafts(current.userId, current.targetKey)
        if len(drafts) == 1:
            current.draftName = tuple(drafts.keys())[0]
    
    # Save the path now so that we can use it again later, even on URLs 
    # (e.g. in AJAX dialogues) that are below this path.
    current.path = current.defaultPath
    
    # Mark context with IDraft
    current.mark()
    current.save()
    
    return current

################################################################################

import zope.schema.interfaces
import zope.lifecycleevent
import zope.event

from zope.interface import implements
from zope.component import adapts
from zope.component import queryUtility
from zope.schema import getFields

from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.interfaces import IDexterityFTI
 
from plone.app.drafts.interfaces import IDraft, IDraftSyncer

from plone.app.drafts.interfaces import IDexterityDraft

class NotFound(object):
    """
    """

class PopulateContentFromDraftSyncer(object):
    """Copy draft persistent dexterity data to the
    real object on save, or vise versa.  This syncer
    is customized to only populate the draft.context
    content object
    """

    implements(IDraftSyncer)
    adapts(IDraft, IDexterityContent)

    # notify of object changes
    notify = True
    
    source = None
    target = None
    portal_type = None
    
    def __init__(self, source, target):
        #self.source = source.context
        self.source = source
        self.target = target
        self.portal_type = getattr( target, 'portal_type', None )

    def __call__(self):
        changes = {}
        
        #fti = queryUtility(IDexterityFTI, self.target.portal_type)
        fti = queryUtility(IDexterityFTI, self.portal_type)
        schema = getFields( fti.lookupSchema() )
        
        for field_name, field_schema in schema.items():
            source_attr = getattr( self.source, field_name, NotFound )
            if source_attr is not NotFound:
                target_attr = getattr( self.target, field_name, NotFound )
                #if target_attr is not NotFound:
                if (source_attr != target_attr 
                    or zope.schema.interfaces.IObject.providedBy(field_schema)):
                    setattr( self.target, field_name, getattr(self.source, field_name) )
                    
                    # Record the change using information required later
                    changes.setdefault(field_schema.interface, []).append(field_name)

        if self.notify:
            if changes:
                descriptions = []
                for interface, names in changes.items():
                    descriptions.append(
                        zope.lifecycleevent.Attributes(interface, *names))
                    
                # Send out a detailed object-modified event
                zope.event.notify(
                    zope.lifecycleevent.ObjectModifiedEvent(self.target,
                        *descriptions))

        return changes

class PopulateDraftFromContextSyncer(PopulateContentFromDraftSyncer):
    implements(IDraftSyncer)
    adapts(IDexterityContent, IDexterityDraft)
    
    def __init__(self, source, target):
        super(PopulateDraftFromContextSyncer, self).__init__(source,target)
        
        portal_type = getattr( source, 'portal_type', None )
        
        # Don't overwrite default set portal type if its None
        if portal_type is not None:
            self.portal_type = portal_type
            
        self.notify = False
        

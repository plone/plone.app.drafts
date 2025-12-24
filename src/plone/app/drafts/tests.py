from plone.app.drafts.draft import Draft
from plone.app.drafts.interfaces import DRAFT_NAME_KEY
from plone.app.drafts.interfaces import ICurrentDraftManagement
from plone.app.drafts.interfaces import IDraft
from plone.app.drafts.interfaces import IDrafting
from plone.app.drafts.interfaces import IDraftProxy
from plone.app.drafts.interfaces import IDraftStorage
from plone.app.drafts.interfaces import IDraftSyncer
from plone.app.drafts.proxy import DraftProxy
from plone.app.drafts.testing import DRAFTS_DX_FUNCTIONAL_TESTING
from plone.app.drafts.testing import DRAFTS_INTEGRATION_TESTING
from plone.app.drafts.utils import getCurrentDraft
from plone.app.drafts.utils import getCurrentUserId
from plone.app.drafts.utils import getDefaultKey
from plone.app.drafts.utils import syncDraft
from plone.app.testing import login
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.dexterity.utils import createContent
from plone.testing.z2 import Browser
from plone.uuid.interfaces import IUUID
from zope.annotation.interfaces import IAnnotations
from zope.component import adapter
from zope.component import getUtility
from zope.component import provideAdapter
from zope.component import queryUtility
from zope.interface import implementer

import transaction
import unittest


class TestSetup(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]

    def test_tool_installed(self):
        self.assertTrue("portal_drafts" in self.portal.objectIds())
        util = queryUtility(IDraftStorage)
        self.assertTrue(IDraftStorage.providedBy(util))


class TestStorage(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def setUp(self):
        self.storage = getUtility(IDraftStorage)

    def test_createDraft(self):
        draft = self.storage.createDraft("user1", "123")
        self.assertTrue(IDraft.providedBy(draft))
        self.assertTrue(draft.__name__ in self.storage.drafts["user1"]["123"])

    def test_createDraft_existing_user_and_key(self):
        draft1 = self.storage.createDraft("user1", "123")
        draft2 = self.storage.createDraft("user1", "123")

        self.assertNotEqual(draft1.__name__, draft2.__name__)
        self.assertTrue(draft1.__name__ in self.storage.drafts["user1"]["123"])
        self.assertTrue(draft2.__name__ in self.storage.drafts["user1"]["123"])

    def test_createDraft_existing_user_only(self):
        draft1 = self.storage.createDraft("user1", "123")
        draft2 = self.storage.createDraft("user1", "345")

        self.assertTrue(draft1.__name__ in self.storage.drafts["user1"]["123"])
        self.assertTrue(draft2.__name__ in self.storage.drafts["user1"]["123"])

    def test_createDraft_factory(self):
        def factory(userId, targetKey):
            return Draft(name="foo")

        draft1 = self.storage.createDraft("user1", "123", factory=factory)
        self.assertEqual("foo", draft1.__name__)
        self.assertTrue(draft1.__name__ in self.storage.drafts["user1"]["123"])

        draft2 = self.storage.createDraft("user1", "123", factory=factory)
        self.assertEqual("foo-1", draft2.__name__)
        self.assertTrue(draft2.__name__ in self.storage.drafts["user1"]["123"])

    def test_discardDrafts(self):
        self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "123")
        self.storage.discardDrafts("user1", "123")
        self.assertFalse("user1" in self.storage.drafts)

    def test_discardDrafts_keep_user(self):
        self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "234")
        self.storage.discardDrafts("user1", "123")

        self.assertTrue("user1" in self.storage.drafts)
        self.assertFalse("123" in self.storage.drafts["user1"])
        self.assertTrue("234" in self.storage.drafts["user1"])

    def test_discardDrafts_all_for_user(self):
        self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "234")
        self.storage.createDraft("user2", "123")
        self.storage.discardDrafts("user1")

        self.assertFalse("user1" in self.storage.drafts)
        self.assertTrue("user2" in self.storage.drafts)
        self.assertTrue("123" in self.storage.drafts["user2"])

    def test_discardDrafts_no_key(self):
        self.storage.createDraft("user1", "123")
        self.storage.discardDrafts("user1", "345")
        self.assertFalse("345" in self.storage.drafts["user1"])

    def test_discardDrafts_no_user(self):
        self.storage.createDraft("user1", "123")
        self.storage.discardDrafts("user2", "123")
        self.assertFalse("user2" in self.storage.drafts)

    def test_discardDraft(self):
        draft = self.storage.createDraft("user1", "123")
        self.storage.discardDraft(draft)
        self.assertFalse("user1" in self.storage.drafts)

    def test_discardDraft_keep_user_and_target(self):
        draft = self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "123")
        self.storage.discardDraft(draft)
        self.assertEqual(1, len(self.storage.drafts["user1"]["123"]))

    def test_discardDraft_keep_user(self):
        draft = self.storage.createDraft("user1", "123")
        self.storage.createDraft("user1", "124")
        self.storage.discardDraft(draft)
        self.assertEqual(1, len(self.storage.drafts["user1"]))
        self.assertTrue("124" in self.storage.drafts["user1"])

    def test_discardDraft_not_found(self):
        self.storage.createDraft("user1", "123")
        draft = Draft("user1", "123", "bogus")
        self.storage.discardDraft(draft)

    def test_discardDraft_no_key(self):
        self.storage.createDraft("user1", "123")
        draft = Draft("user1", "234", "draft")
        self.storage.discardDraft(draft)

    def test_discardDraft_no_user(self):
        self.storage.createDraft("user1", "123")
        draft = Draft("user2", "123", "draft")
        self.storage.discardDraft(draft)

    def test_getDrafts(self):
        draft1 = self.storage.createDraft("user1", "123")
        draft2 = self.storage.createDraft("user1", "123")

        drafts = self.storage.getDrafts("user1", "123")
        self.assertEqual(drafts[draft1.__name__], draft1)
        self.assertEqual(drafts[draft2.__name__], draft2)

    def test_getDrafts_no_user(self):
        self.storage.createDraft("user1", "123")
        drafts = self.storage.getDrafts("user2", "123")
        self.assertEqual(0, len(drafts))

    def test_getDrafts_no_key(self):
        self.storage.createDraft("user1", "123")
        drafts = self.storage.getDrafts("user2", "234")
        self.assertEqual(0, len(drafts))

    def test_getDraft_found(self):
        draft = self.storage.createDraft("user1", "123")
        self.assertEqual(draft, self.storage.getDraft("user1", "123", draft.__name__))

    def test_getDraft_not_found(self):
        self.storage.createDraft("user1", "123")
        self.assertEqual(None, self.storage.getDraft("user1", "123", "bogus"))

    def test_getDraft_no_key(self):
        draft = self.storage.createDraft("user1", "123")
        self.assertEqual(None, self.storage.getDraft("user1", "234", draft.__name__))

    def test_getDraft_no_user(self):
        draft = self.storage.createDraft("user1", "123")
        self.assertEqual(None, self.storage.getDraft("user2", "123", draft.__name__))


class TestDraftProxy(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]

        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        login(self.portal, TEST_USER_NAME)

        self.portal.invokeFactory("Folder", "folder")
        self.folder = self.portal["folder"]

    def test_attributes(self):

        self.folder.invokeFactory("Document", "d1")
        target = self.folder["d1"]

        target.title = "Old title"

        draft = Draft()
        draft.someAttribute = 1

        proxy = DraftProxy(draft, target)

        self.assertEqual("Old title", proxy.title)
        self.assertEqual(1, proxy.someAttribute)

        proxy.title = "New title"

        self.assertEqual("New title", proxy.title)

    def test_attribute_deletion(self):

        self.folder.invokeFactory("Document", "d1")
        target = self.folder["d1"]

        target.title = "Old title"
        target.description = "Old description"

        draft = Draft()

        draft.someAttribute = 1
        draft.description = "New description"

        proxy = DraftProxy(draft, target)

        del proxy.someAttribute
        del proxy.title
        del proxy.description

        self.assertEqual(
            {"someAttribute", "title", "description"},
            draft._proxyDeleted,
        )

        self.assertFalse(hasattr(draft, "someAttribute"))
        self.assertFalse(hasattr(draft, "title"))
        self.assertFalse(hasattr(draft, "description"))

        self.assertFalse(hasattr(proxy, "someAttribute"))
        self.assertFalse(hasattr(proxy, "title"))
        self.assertFalse(hasattr(proxy, "description"))

        self.assertEqual("Old title", target.title)
        self.assertEqual("Old description", target.description)

    def test_interfaces(self):

        self.folder.invokeFactory("Document", "d1")
        target = self.folder["d1"]

        draft = Draft()
        proxy = DraftProxy(draft, target)

        self.assertFalse(IDraft.providedBy(proxy))
        self.assertTrue(IDraftProxy.providedBy(proxy))

        from plone.app.contenttypes.interfaces import IDocument

        self.assertTrue(IDocument.providedBy(proxy))

    def test_annotations(self):

        self.folder.invokeFactory("Document", "d1")
        target = self.folder["d1"]

        targetAnnotations = IAnnotations(target)
        targetAnnotations["test.key"] = 123
        targetAnnotations["other.key"] = 456

        draft = Draft()

        draftAnnotations = IAnnotations(draft)
        draftAnnotations["some.key"] = 234

        proxy = DraftProxy(draft, target)

        proxyAnnotations = IAnnotations(proxy)

        self.assertEqual(123, proxyAnnotations["test.key"])
        self.assertEqual(234, proxyAnnotations["some.key"])

        proxyAnnotations["test.key"] = 789

        self.assertEqual(789, proxyAnnotations["test.key"])
        self.assertEqual(123, targetAnnotations["test.key"])

        # Annotations API

        self.assertEqual(789, proxyAnnotations.get("test.key"))

        keys = proxyAnnotations.keys()
        self.assertTrue("test.key" in keys)
        self.assertTrue("some.key" in keys)
        self.assertTrue("other.key" in keys)

        self.assertEqual(789, proxyAnnotations.setdefault("test.key", -1))
        self.assertEqual(234, proxyAnnotations.setdefault("some.key", -1))
        self.assertEqual(456, proxyAnnotations.setdefault("other.key", -1))
        self.assertEqual(-1, proxyAnnotations.setdefault("new.key", -1))

        del proxyAnnotations["test.key"]
        self.assertFalse("test.key" in proxyAnnotations)
        self.assertFalse("test.key" in draftAnnotations)
        self.assertTrue("test.key" in targetAnnotations)
        self.assertTrue("test.key" in draft._proxyAnnotationsDeleted)

        del proxyAnnotations["some.key"]
        self.assertFalse("some.key" in proxyAnnotations)
        self.assertFalse("some.key" in draftAnnotations)
        self.assertFalse("some.key" in targetAnnotations)
        self.assertTrue("some.key" in draft._proxyAnnotationsDeleted)

        # this key was never in the proxy/draft
        del proxyAnnotations["other.key"]
        self.assertFalse("other.key" in proxyAnnotations)
        self.assertFalse("other.key" in draftAnnotations)
        self.assertTrue("other.key" in targetAnnotations)
        self.assertTrue("other.key" in draft._proxyAnnotationsDeleted)


class TestDraftSyncer(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def test_syncDraft(self):
        class Target:
            pass

        draft = Draft()
        draft.a1 = 1
        draft.a2 = 2

        target = Target()

        @adapter(Draft, Target)
        @implementer(IDraftSyncer)
        class Syncer1:
            def __init__(self, draft, target):
                self.draft = draft
                self.target = target

            def __call__(self):
                self.target.a1 = self.draft.a1

        provideAdapter(Syncer1, name="s1")

        @adapter(Draft, Target)
        @implementer(IDraftSyncer)
        class Syncer2:
            def __init__(self, draft, target):
                self.draft = draft
                self.target = target

            def __call__(self):
                self.target.a2 = self.draft.a2

        provideAdapter(Syncer2, name="s2")

        syncDraft(draft, target)

        self.assertEqual(1, target.a1)
        self.assertEqual(2, target.a2)


class TestCurrentDraft(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def setUp(self):
        self.request = self.layer["request"]

    def test_userId(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        self.assertEqual(TEST_USER_ID, current.userId)

        current.userId = "third-user"
        self.assertEqual("third-user", current.userId)

    def test_targetKey(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        self.assertEqual(None, current.targetKey)

        request.set("plone.app.drafts.targetKey", "123")
        self.assertEqual("123", current.targetKey)

        current.targetKey = "234"
        self.assertEqual("234", current.targetKey)

        self.assertEqual("123", request.get("plone.app.drafts.targetKey"))

    def test_draftName(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        self.assertEqual(None, current.draftName)

        request.set("plone.app.drafts.draftName", "draft-1")
        self.assertEqual("draft-1", current.draftName)

        current.draftName = "draft-2"
        self.assertEqual("draft-2", current.draftName)

        self.assertEqual("draft-1", request.get("plone.app.drafts.draftName"))

    def test_path(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        self.assertEqual(None, current.path)

        request.set("plone.app.drafts.path", "/test")
        self.assertEqual("/test", current.path)

        current.path = "/test/test-1"
        self.assertEqual("/test/test-1", current.path)

        self.assertEqual("/test", request.get("plone.app.drafts.path"))

    def test_draft(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        self.assertEqual(None, current.draft)

        current.userId = "user1"
        current.targetKey = "123"
        current.draftName = "draft"

        self.assertEqual(None, current.draft)

        storage = getUtility(IDraftStorage)
        created = storage.createDraft("user1", "123")
        current.draftName = created.__name__

        self.assertEqual(created, current.draft)

        newDraft = storage.createDraft("user1", "123")
        current.draft = newDraft

        self.assertEqual(newDraft, current.draft)

    def test_defaultPath(self):
        request = self.request

        request["URL"] = "http://nohost"

        current = ICurrentDraftManagement(request)
        self.assertEqual("/", current.defaultPath)

        request["URL"] = "http://nohost/"
        self.assertEqual("/", current.defaultPath)

        request["URL"] = "http://nohost/test/edit"
        self.assertEqual("/test", current.defaultPath)

        request["URL"] = "http://nohost/test/edit/"
        self.assertEqual("/test/edit", current.defaultPath)

    def test_mark(self):
        request = self.request

        current = ICurrentDraftManagement(request)
        current.mark()
        self.assertFalse(IDrafting.providedBy(request))

        current.targetKey = "123"
        current.mark()
        self.assertTrue(IDrafting.providedBy(request))

    def test_save(self):
        request = self.request
        response = request.response

        current = ICurrentDraftManagement(request)
        self.assertEqual(False, current.save())

        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)
        self.assertFalse("plone.app.drafts.userId" in response.cookies)
        self.assertFalse("plone.app.drafts.path" in response.cookies)

        current.targetKey = "123"
        self.assertEqual(True, current.save())

        self.assertEqual(
            {"value": "123", "Path": "/"},
            response.cookies["plone.app.drafts.targetKey"],
        )
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)
        self.assertFalse("plone.app.drafts.path" in response.cookies)

        current.targetKey = "123"
        current.draftName = "draft-1"
        self.assertEqual(True, current.save())

        self.assertEqual(
            {"value": "123", "Path": "/"},
            response.cookies["plone.app.drafts.targetKey"],
        )
        self.assertEqual(
            {"value": "draft-1", "Path": "/"},
            response.cookies["plone.app.drafts.draftName"],
        )
        self.assertFalse("plone.app.drafts.path" in response.cookies)

        current.targetKey = "123"
        current.draftName = "draft-1"
        current.path = "/test"

        # clear data
        del self.request.response.cookies["plone.app.drafts.targetKey"]
        del self.request.response.cookies["plone.app.drafts.draftName"]

        self.assertEqual(True, current.save())

        self.assertEqual(
            {"value": "123", "Path": "/test"},
            response.cookies["plone.app.drafts.targetKey"],
        )
        self.assertEqual(
            {"value": "draft-1", "Path": "/test"},
            response.cookies["plone.app.drafts.draftName"],
        )
        self.assertEqual(
            {"value": "/test", "Path": "/test"},
            response.cookies["plone.app.drafts.path"],
        )

    def test_discard(self):
        request = self.request
        response = request.response

        current = ICurrentDraftManagement(request)
        current.discard()

        deletedToken = {
            "Expires": "Wed, 31 Dec 1997 23:59:59 GMT",
            "Max-Age": "0",
            "Path": "/",
            "value": "deleted",
        }

        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.targetKey"],
        )
        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.draftName"],
        )
        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.path"],
        )

        current.path = "/test"
        current.discard()

        deletedToken["Path"] = "/test"

        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.targetKey"],
        )
        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.draftName"],
        )
        self.assertEqual(
            deletedToken,
            response.cookies["plone.app.drafts.path"],
        )


class TestUtils(unittest.TestCase):

    layer = DRAFTS_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]

        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        login(self.portal, TEST_USER_NAME)

        self.portal.invokeFactory("Folder", "folder")
        self.folder = self.portal["folder"]
        self.request = self.layer["request"]

    def test_getUserId(self):
        self.assertEqual(TEST_USER_ID, getCurrentUserId())

    def test_getUserId_anonymous(self):
        logout()
        self.assertEqual(None, getCurrentUserId())

    def test_getDefaultKey(self):
        uuid = IUUID(self.folder)
        self.assertEqual(str(uuid), getDefaultKey(self.folder))

    def test_getCurrentDraft_not_set_no_create(self):
        request = self.request
        draft = getCurrentDraft(request)
        self.assertEqual(None, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_not_set_no_details_create(self):
        request = self.request
        draft = getCurrentDraft(request, create=True)
        self.assertEqual(None, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_draft_set(self):
        request = self.request

        management = ICurrentDraftManagement(request)
        management.draft = setDraft = Draft()

        draft = getCurrentDraft(request)
        self.assertEqual(setDraft, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_draft_set_create(self):
        request = self.request

        management = ICurrentDraftManagement(request)
        management.draft = setDraft = Draft()

        draft = getCurrentDraft(request, create=True)
        self.assertEqual(setDraft, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_draft_details_set_not_in_storage(self):
        request = self.request

        management = ICurrentDraftManagement(request)
        management.userId = "user1"
        management.targetKey = "123"
        management.draftName = "bogus"

        draft = getCurrentDraft(request)
        self.assertEqual(None, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_draft_details_set_not_in_storage_create(self):
        request = self.request

        management = ICurrentDraftManagement(request)
        management.userId = "user1"
        management.targetKey = "123"
        management.draftName = "bogus"

        draft = getCurrentDraft(request, create=True)
        inStorage = getUtility(IDraftStorage).getDraft("user1", "123", draft.__name__)

        self.assertEqual(inStorage, draft)

        response = request.response
        self.assertTrue("plone.app.drafts.targetKey" in response.cookies)
        self.assertTrue("plone.app.drafts.draftName" in response.cookies)

        self.assertEqual(
            "123",
            response.cookies["plone.app.drafts.targetKey"]["value"],
        )
        self.assertEqual(
            draft.__name__,
            response.cookies["plone.app.drafts.draftName"]["value"],
        )

    def test_getCurrentDraft_draft_details_set_in_storage(self):
        request = self.request

        inStorage = getUtility(IDraftStorage).createDraft("user1", "123")

        management = ICurrentDraftManagement(request)
        management.userId = "user1"
        management.targetKey = "123"
        management.draftName = inStorage.__name__

        draft = getCurrentDraft(request)
        self.assertEqual(inStorage, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)

    def test_getCurrentDraft_draft_details_set_in_storage_create(self):
        request = self.request

        inStorage = getUtility(IDraftStorage).createDraft("user1", "123")

        management = ICurrentDraftManagement(request)
        management.userId = "user1"
        management.targetKey = "123"
        management.draftName = inStorage.__name__

        draft = getCurrentDraft(request, create=True)
        self.assertEqual(inStorage, draft)

        response = request.response
        self.assertFalse("plone.app.drafts.targetKey" in response.cookies)
        self.assertFalse("plone.app.drafts.draftName" in response.cookies)


class TestDexterityIntegration(unittest.TestCase):

    layer = DRAFTS_DX_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]

        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        login(self.portal, TEST_USER_NAME)

        self.portal.invokeFactory("Folder", "folder")
        self.folder = self.portal["folder"]

        transaction.commit()

    def get_portal_target_key(self):
        try:
            # Plone 6
            return IUUID(self.portal)
        except TypeError:
            # Plone <6
            return "%2B%2Badd%2B%2BMyDocument"

    def test_add_to_portal_root_cancel(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the add screen for a temporary portal_factory-managed object
        browser.open(self.portal.absolute_url() + "/++add++MyDocument")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual("/plone", cookies["plone.app.drafts.path"])
        self.assertEqual(
            f"{self.get_portal_target_key()}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

        # We can now cancel the edit. The cookies should expire.
        browser.getControl(name="form.buttons.cancel").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

    def test_add_to_portal_root_save(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the add screen for a temporary portal_factory-managed object
        browser.open(self.portal.absolute_url() + "/++add++MyDocument")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual("/plone", cookies["plone.app.drafts.path"])
        self.assertEqual(
            f"{self.get_portal_target_key()}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

        # Simulate save action for creating a draft
        storage = queryUtility(IDraftStorage)
        draft = storage.createDraft(TEST_USER_ID, "++add++MyDocument")
        target = createContent("MyDocument")
        draft._draftAddFormTarget = target
        transaction.commit()

        browser.cookies.create(
            DRAFT_NAME_KEY,
            "draft",
            path="/plone",
        )

        # We can now fill in the required fields and save. The cookies should
        # expire.

        browser.getControl(name="form.widgets.IDublinCore.title").value = "New Document"
        browser.getControl(name="form.buttons.save").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

    def test_add_to_folder(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the add screen for a temporary portal_factory-managed object
        browser.open(self.folder.absolute_url() + "/++add++MyDocument")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual(
            f"{self.folder.absolute_url_path()}",
            cookies["plone.app.drafts.path"],
        )
        self.assertEqual(
            f"{IUUID(self.folder)}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

        # We can now cancel the edit. The cookies should expire.
        browser.getControl(name="form.buttons.cancel").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )

    def test_edit(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        self.folder.invokeFactory("MyDocument", "d1")
        self.folder["d1"].title = "New title"

        transaction.commit()

        uuid = IUUID(self.folder["d1"])

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the edit screen
        browser.open(self.folder["d1"].absolute_url() + "/edit")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual(
            "{}".format(self.folder["d1"].absolute_url_path()),
            cookies["plone.app.drafts.path"],
        )
        self.assertEqual(
            f"{uuid}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

        # We can now save the page. The cookies should expire.
        browser.getControl(name="form.buttons.save").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

    def test_edit_existing_draft(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        self.folder.invokeFactory("MyDocument", "d1")
        self.folder["d1"].title = "New title"

        uuid = IUUID(self.folder["d1"])

        # Create a single draft for this object - we expect this to be used now
        storage = getUtility(IDraftStorage)
        draft = storage.createDraft(TEST_USER_ID, str(uuid))

        transaction.commit()

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the edit screen
        browser.open(self.folder["d1"].absolute_url() + "/edit")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual(
            "{}".format(self.folder["d1"].absolute_url_path()),
            cookies["plone.app.drafts.path"],
        )
        self.assertEqual(
            f"{uuid}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertEqual(
            f"{TEST_USER_ID}",
            cookies["plone.app.drafts.userId"],
        )
        self.assertEqual(
            f"{draft.__name__}",
            cookies["plone.app.drafts.draftName"],
        )

        # We can now save the page. The cookies should expire.
        browser.getControl(name="form.buttons.save").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.userId",
            browser.cookies.forURL(browser.url),
        )

    def test_edit_multiple_existing_drafts(self):
        browser = Browser(self.layer["app"])
        browser.handleErrors = False

        self.folder.invokeFactory("MyDocument", "d1")
        self.folder["d1"].title = "New title"

        transaction.commit()

        uuid = IUUID(self.folder["d1"])

        # Create two drafts for this object - we don't expect either to be used
        storage = getUtility(IDraftStorage)
        storage.createDraft(TEST_USER_ID, str(uuid))
        storage.createDraft(TEST_USER_ID, str(uuid))

        # Login
        browser.open(self.portal.absolute_url() + "/login")
        browser.getControl(name="__ac_name").value = TEST_USER_NAME
        browser.getControl(name="__ac_password").value = TEST_USER_PASSWORD
        browser.getControl("Log in").click()

        # Enter the edit screen
        browser.open(self.folder["d1"].absolute_url() + "/edit")

        # We should now have cookies with the drafts information
        cookies = browser.cookies.forURL(browser.url)
        self.assertEqual(
            "{}".format(self.folder["d1"].absolute_url_path()),
            cookies["plone.app.drafts.path"],
        )
        self.assertEqual(
            f"{uuid}",
            cookies["plone.app.drafts.targetKey"],
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

        # We can now save the page. The cookies should expire.
        browser.getControl(name="form.buttons.save").click()
        self.assertNotIn(
            "plone.app.drafts.targetKey",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.path",
            browser.cookies.forURL(browser.url),
        )
        self.assertNotIn(
            "plone.app.drafts.draftName",
            browser.cookies.forURL(browser.url),
        )

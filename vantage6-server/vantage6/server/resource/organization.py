# -*- coding: utf-8 -*-
import logging

from flask import request, g
from flask_restful import Api
from http import HTTPStatus

from vantage6.common import logger_name
from vantage6.server import db
from vantage6.server.resource.common.pagination import Pagination
from vantage6.server.permission import (
    Scope as S,
    Operation as P,
    PermissionManager
)
from vantage6.server.resource import (
    only_for, with_user, ServicesResources
)
from vantage6.server.resource.common._schema import OrganizationSchema

module_name = logger_name(__name__)
log = logging.getLogger(module_name)


def setup(api: Api, api_base: str, services: dict) -> None:
    """
    Setup the organization resource.

    Parameters
    ----------
    api : Api
        Flask restful api instance
    api_base : str
        Base url of the api
    services : dict
        Dictionary with services required for the resource endpoints
    """
    path = "/".join([api_base, module_name])
    log.info(f'Setting up "{path}" and subdirectories')

    api.add_resource(
        Organizations,
        path,
        endpoint='organization_without_id',
        methods=('GET', 'POST'),
        resource_class_kwargs=services
     )
    api.add_resource(
        Organization,
        path + '/<int:id>',
        endpoint='organization_with_id',
        methods=('GET', 'PATCH'),
        resource_class_kwargs=services
    )


# -----------------------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------------------
def permissions(permissions: PermissionManager) -> None:
    """
    Define the permissions for this resource.

    Parameters
    ----------
    permissions : PermissionManager
        Permission manager instance to which permissions are added
    """
    add = permissions.appender(module_name)

    add(scope=S.GLOBAL, operation=P.VIEW,
        description="view any organization")
    add(scope=S.ORGANIZATION, operation=P.VIEW,
        description="view your own organization info",
        assign_to_container=True, assign_to_node=True)
    add(scope=S.COLLABORATION, operation=P.VIEW,
        description='view collaborating organizations',
        assign_to_container=True, assign_to_node=True)
    add(scope=S.GLOBAL, operation=P.EDIT,
        description="edit any organization")
    add(scope=S.ORGANIZATION, operation=P.EDIT,
        description="edit your own organization info", assign_to_node=True)
    add(scope=S.GLOBAL, operation=P.CREATE,
        description="create a new organization")


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------
org_schema = OrganizationSchema()


class OrganizationBase(ServicesResources):

    def __init__(self, socketio, mail, api, permissions, config):
        super().__init__(socketio, mail, api, permissions, config)
        self.r = getattr(self.permissions, module_name)


class Organizations(OrganizationBase):

    @only_for(("user", "node", "container"))
    def get(self):
        """ Returns a list organizations
        ---
        description: >-
            Get a list of organizations based on filters and user permissions\n

            ### Permission Table\n
            |Rule name|Scope|Operation|Assigned to node|Assigned to container|
            Description|\n
            |--|--|--|--|--|--|\n
            |Organization|Global|View|❌|❌|View all organizations|\n
            |Organization|Collaboration|View|✅|✅|View a list of organizations
            within the scope of the collaboration|\n
            |Organization|Organization|View|✅|✅|View a 'list' of just the
            organization you are part of|\n

            Accessible to users.

        parameters:
          - in: query
            name: name
            schema:
              type: string
            description: >-
              Name to match with a LIKE operator. \n
              * The percent sign (%) represents zero, one, or multiple
              characters\n
              * underscore sign (_) represents one, single character
          - in: query
            name: country
            schema:
              type: string
            description: Country
          - in: query
            name: collaboration_id
            schema:
              type: integer
            description: Collaboration id
          - in: query
            name: page
            schema:
              type: integer
            description: Page number for pagination (default=1)
          - in: query
            name: per_page
            schema:
              type: integer
            description: Number of items per page (default=10)
          - in: query
            name: sort
            schema:
              type: string
            description: >-
              Sort by one or more fields, separated by a comma. Use a minus
              sign (-) in front of the field to sort in descending order.

        responses:
          200:
            description: Ok
          401:
            description: Unauthorized
          400:
            description: Improper values for pagination or sorting parameters

        security:
          - bearerAuth: []

        tags: ["Organization"]
        """

        # Obtain the organization of the requester
        auth_org = self.obtain_auth_organization()
        args = request.args

        # query
        q = g.session.query(db.Organization)
        g.session.commit()

        # filter by a field of this endpoint
        if 'name' in args:
            q = q.filter(db.Organization.name.like(args['name']))
        if 'country' in args:
            q = q.filter(db.Organization.country == args['country'])
        if 'collaboration_id' in args:
            q = q.join(db.Member).join(db.Collaboration)\
                 .filter(db.Collaboration.id == args['collaboration_id'])

        # filter the list of organizations based on the scope
        if self.r.v_glo.can():
            pass  # don't apply filters
        elif self.r.v_col.can():
            # obtain collaborations your organization participates in
            collabs = g.session.query(db.Collaboration).filter(
                db.Collaboration.organizations.any(id=auth_org.id)
            ).all()
            g.session.commit()

            # list comprehension fetish, and add own organization in case
            # this organization does not participate in any collaborations yet
            org_ids = [o.id for col in collabs for o in col.organizations]
            org_ids = list(set(org_ids + [auth_org.id]))

            # select only the organizations in the collaborations
            q = q.filter(db.Organization.id.in_(org_ids))

        elif self.r.v_org.can():
            q = q.filter(db.Organization.id == auth_org.id)
        else:
            return {'msg': 'You lack the permission to do that!'}, \
                HTTPStatus.UNAUTHORIZED

        # paginate the results
        try:
            page = Pagination.from_query(query=q, request=request)
        except ValueError as e:
            return {'msg': str(e)}, HTTPStatus.BAD_REQUEST

        # serialization of DB model
        return self.response(page, org_schema)

    @with_user
    def post(self):
        """Create new organization
        ---
        description: >-
          Creates a new organization from the specified values\n

          ### Permission Table\n
          |Rule name|Scope|Operation|Assigned to node|Assigned to container|
          Description|\n
          |--|--|--|--|--|--|\n
          |Organization|Global|Create|❌|❌|Create a new organization|\n

          Accessible to users.

        requestBody:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Organization'

        responses:
          201:
            description: Ok
          401:
            description: Unauthorized
          400:
            description: Organization with that name already exists

        security:
          - bearerAuth: []

        tags: ["Organization"]
        """

        if not self.r.c_glo.can():
            return {'msg': 'You lack the permissions to do that!'},\
                HTTPStatus.UNAUTHORIZED

        data = request.get_json()
        name = data.get('name', '')
        if db.Organization.exists("name", name):
            return {
                "msg": f"Organization with name '{name}' already exists!"
            }, HTTPStatus.BAD_REQUEST

        organization = db.Organization(
            name=name,
            address1=data.get('address1', ''),
            address2=data.get('address2' ''),
            zipcode=data.get('zipcode', ''),
            country=data.get('country', ''),
            public_key=data.get('public_key', ''),
            domain=data.get('domain', '')
        )
        organization.save()

        return org_schema.dump(organization, many=False).data, \
            HTTPStatus.CREATED


class Organization(OrganizationBase):

    @only_for(("user", "node", "container"))
    def get(self, id):
        """Get organization
        ---
        description: >-
          Returns the organization specified by the id\n

          ### Permission Table\n
          |Rule name|Scope|Operation|Assigned to node|Assigned to container|
          Description|\n
          |--|--|--|--|--|--|\n
          |Organization|Global|View|❌|❌|View all organizations|\n
          |Organization|Collaboration|View|✅|✅|View a list of organizations
          within the scope of the collaboration|\n
          |Organization|Organization|View|✅|✅|View a list of organizations
          that the user is part of|\n

          Accessible to users.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            description: Organization id
            required: true

        responses:
          200:
            description: Ok
          404:
            description: Organization not found
          401:
            description: Unauthorized

        security:
          - bearerAuth: []

        tags: ["Organization"]
        """

        # obtain organization of authenticated
        auth_org = self.obtain_auth_organization()

        # retrieve requested organization
        req_org = db.Organization.get(id)
        if not req_org:
            return {'msg': f'Organization id={id} not found!'}, \
                HTTPStatus.NOT_FOUND

        accepted = False
        # Check if auth has enough permissions
        if self.r.v_glo.can():
            accepted = True
        elif self.r.v_col.can():
            # check if the organization is whithin a collaboration
            for col in auth_org.collaborations:
                if req_org in col.organizations:
                    accepted = True
            # or that the organization is auths org
            if req_org == auth_org:
                accepted = True
        elif self.r.v_org.can():
            accepted = auth_org == req_org

        if accepted:
            return org_schema.dump(req_org, many=False).data, \
                HTTPStatus.OK
        else:
            return {'msg': 'You do not have permission to do that!'}, \
                HTTPStatus.UNAUTHORIZED

    @only_for(("user", "node"))
    def patch(self, id):
        """Update organization
        ---
        description: >-
          Updates the organization with the specified id.\n

          ### Permission Table\n
          |Rule name|Scope|Operation|Assigned to node|Assigned to container|
          Description|\n
          |--|--|--|--|--|--|\n
          |Organization|Global|Edit|❌|❌|Update an organization with
          specified id|\n
          |Organization|Organization|Edit|❌|❌|Update the organization that
          the user is part of|\n

          Accessible to users.

        parameters:
          - in: path
            name: id
            schema:
              type: integer
            description: Organization id
            required: tr

        requestBody:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Organization'

        responses:
          200:
            description: Ok
          404:
            description: Organization with specified id is not found
          401:
            description: Unauthorized
          400:
            description: Organization with that name already exists

        security:
          - bearerAuth: []

        tags: ["Organization"]
        """

        organization = db.Organization.get(id)
        if not organization:
            return {"msg": f"Organization with id={id} not found"}, \
                HTTPStatus.NOT_FOUND

        if not (
            self.r.e_glo.can() or
            (self.r.e_org.can() and g.user and id == g.user.organization.id) or
            (self.r.e_org.can() and g.node and id == g.node.organization.id)
        ):
            return {'msg': 'You lack the permission to do that!'}, \
                HTTPStatus.UNAUTHORIZED

        data = request.get_json()
        name = data.get('name', None)
        if name:
            if organization.name != name and \
                    db.Organization.exists("name", name):
                return {
                    "msg": f"Organization with name '{name}' already exists!"
                }, HTTPStatus.BAD_REQUEST
            organization.name = name

        fields = ["address1", "address2", "zipcode", "country",
                  "public_key", "domain"]
        for field in fields:
            if field in data and data[field] is not None:
                setattr(organization, field, data[field])

        organization.save()
        return org_schema.dump(organization, many=False).data, \
            HTTPStatus.OK

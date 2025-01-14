from __future__ import annotations

import math
import logging
import flask
import sqlalchemy

from urllib.parse import urlencode

from vantage6.common import logger_name
from vantage6.server.globals import DEFAULT_PAGE, DEFAULT_PAGE_SIZE
from vantage6.server import db

module_name = logger_name(__name__)
log = logging.getLogger(module_name)


class Page:
    """
    Definition of a page of items return by the API.

    Parameters
    ----------
    items : list[db.Base]
        List of database resources on this page
    page : int
        Current page number
    page_size : int
        Number of items per page
    total : int
        Total number of items

    Attributes
    ----------
    current_page : int
        Current page number
    items : list[db.Base]
        List of resources on the current page
    previous_page : int
        Page number of the previous page
    next_page : int
        Page number of the next page
    has_previous : bool
        True if there is a previous page, False otherwise
    has_next : bool
        True if there is a next page, False otherwise
    total : int
        Total number of items
    pages : int
        Total number of pages
    """
    def __init__(self, items: list[db.Base], page: int, page_size: int,
                 total: int) -> None:
        self.current_page = page
        self.items = items
        self.previous_page = None
        self.next_page = None
        self.has_previous = page > 1
        if self.has_previous:
            self.previous_page = page - 1
        previous_items = (page - 1) * page_size
        self.has_next = previous_items + len(items) < total
        if self.has_next:
            self.next_page = page + 1
        self.total = total
        self.pages = int(math.ceil(total / float(page_size)))


class Pagination:
    """
    Class that handles pagination of a query.

    Parameters
    ----------
    items : list[db.Base]
        List of database resources to paginate
    page : int
        Current page number
    page_size : int
        Number of items per page
    total : int
        Total number of items
    request : flask.Request
        Request object

    Attributes
    ----------
    page : Page
        Page object
    request : flask.Request
        Request object
    """
    def __init__(self, items: list[db.Base], page: int, page_size: int,
                 total: int, request: flask.Request) -> None:
        self.page = Page(items, page, page_size, total)
        self.request = request

    @property
    def link_header(self) -> str:
        """
        Puts links to other pages in the response header.

        Returns
        -------
        str
            Link header
        """
        link_strs = [f'<{url}>; rel={rel}' for rel, url in
                     self.metadata_links.items()]
        return ','.join(link_strs)

    @property
    def headers(self) -> dict:
        """
        Set the headers for the response.

        Returns
        -------
        dict
            Response headers
        """
        return {
            'total-count': self.page.total,
            'Link': self.link_header,
            # indicate that these headers are allowed to be exposed to scripts
            # running in a browser
            'access-control-expose-headers': 'total-count, Link',
        }

    @property
    def metadata_links(self) -> dict:
        """
        Construct links to other pages.

        Returns
        -------
        dict
            Links to other pages
        """
        url = self.request.path
        args = self.request.args.copy()

        navs = [
            {'rel': 'first', 'page': 1},
            {'rel': 'previous', 'page': self.page.previous_page},
            {'rel': 'self', 'page': self.page.current_page},
            {'rel': 'next', 'page': self.page.next_page},
            {'rel': 'last', 'page': self.page.pages},
        ]

        links = {}
        for nav in navs:
            if nav['page']:
                args['page'] = nav['page']
                links[nav['rel']] = f'{url}?{urlencode(args)}'

        return links

    @classmethod
    def from_query(
        cls, query: sqlalchemy.orm.query, request: flask.Request,
        paginate: bool = True
    ) -> Pagination:
        """
        Create a Pagination object from a query.

        Parameters
        ----------
        query : sqlalchemy.orm.query
            Query to paginate
        request : flask.Request
            Request object
        paginate : bool
            Whether to paginate the query or not, default True

        Returns
        -------
        Pagination
            Pagination object
        """
        # We remove the ordering of the query since it doesn't matter for
        # getting a count and might have performance implications as discussed
        # on this Flask-SqlAlchemy issue
        # https://github.com/mitsuhiko/flask-sqlalchemy/issues/100
        total = query.distinct().order_by(None).count()

        # check if pagination is desired, else return all records
        if paginate:
            page_id = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))

            if page_id <= 0:
                raise AttributeError('page needs to be >= 1')
            if per_page <= 0:
                raise AttributeError('per_page needs to be >= 1')
        else:
            page_id = 1
            per_page = total or 1

        # FIXME BvB 2020-02-09 good error handling if sort is not a valid
        #  field
        if request.args.get('sort', False):
            query = cls._add_sorting(query, request.args.get('sort'))

        items = query.distinct().limit(per_page).offset((page_id-1)*per_page)\
            .all()

        return cls(items, page_id, per_page, total, request)

    @staticmethod
    def _get_page_id(request: flask.Request) -> int:
        """
        Get the page id from the request.

        Parameters
        ----------
        request : flask.Request
            Request object

        Returns
        -------
        int
            Page id

        Raises
        ------
        ValueError
            If the page id is not an integer or is less than 1
        """
        try:
            page_id = int(request.args.get('page', DEFAULT_PAGE))
        except ValueError:
            raise ValueError("The 'page' parameter should be an integer")
        if page_id <= 0:
            raise ValueError("The 'page' parameter should be >= 1")
        return page_id

    @staticmethod
    def _get_per_page(request: flask.Request) -> int:
        """
        Get the number of items per page from the request.

        Parameters
        ----------
        request : flask.Request
            Request object

        Returns
        -------
        int
            Number of items per page

        Raises
        ------
        ValueError
            If the number of items per page is not an integer or is less than 1
        """
        try:
            per_page = int(request.args.get('per_page', DEFAULT_PAGE_SIZE))
        except ValueError:
            raise ValueError("The 'per_page' parameter should be an integer")
        if per_page <= 0:
            raise ValueError("The 'per_page' parameter should be >= 1")
        return per_page

    @staticmethod
    def _add_sorting(query: sqlalchemy.orm.query, sort_string: str
                     ) -> sqlalchemy.orm.query:
        """
        Add sorting to a query.

        Parameters
        ----------
        query : sqlalchemy.orm.query
            The query to add sorting to.
        sort : str
            The sorting to add. This can be a comma separated list of fields to
            sort on. The fields can be prefixed with a '-' to indicate a
            descending sort.
        """
        sort_list = sort_string.split(',')
        for sorter in sort_list:
            sorter = sorter.strip()
            if sorter.startswith('-'):
                query = query.order_by(sqlalchemy.desc(sorter[1:]))
            else:
                if sorter.startswith('+'):
                    sorter = sorter[1:]
                query = query.order_by(sorter)
        return query

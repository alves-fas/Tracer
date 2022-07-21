from __future__ import annotations

from typing import Any, AsyncGenerator, Callable, Dict, Generator, Tuple, Optional
import asyncio
import copy

from aiohttp import ClientSession

from .website import Website
from .result import Result


class WebsitePool(object):
    """Represents a collection of `tracer.Website` instances

    Attributes
    ----------
    sites : Tuple[tracer.Website]
        All websites that are currently in the pool
    name : Optional[str]
        The name of the pool
    results : Tuple[tracer.Result]
        A collection of available results

    Methods
    -------
    obj.set_name(str) -> None
        Sets the name of the pool
    obj.set_username(str) -> None
        Sets the username for every website inside the pool
    obj.add(tracer.Website) -> None
        Adds a website to the pool
    obj.remove(Callable[[tracer.Website], bool]) -> None
        Removes websites from the pool
    obj.start_requests(aiohttp.ClientSession, Optional[float]) -> AsyncGenerator[Result, None]
        Calls `send_request` of every site inside of the pool

    Supported Operations
    --------------------
    `str(obj)`
        Returns the str representation of the pool
    `len(obj)`
        Returns the amount of websites that are currently in the pool
    `iter(obj)`
        Returns a generator containing all websites that are currently in the pool
    `x in obj`
        Checks if a website is currently in the pool
    `copy.copy(obj)`
        Returns a copy of the pool
    `copy.deepcopy(obj)`
        Returns a deepcopy of the pool

    Example
    -------
    >>> pool = WebsitePool(*my_websites, name="MyPool")

    >>> pool.add(website)

    >>> async for result in pool.start_requests(session, timeout=1):

    >>>     print(result)

    Author
    ------
    chr3st5an
    """

    def __init__(self, *sites: Website, name: Optional[str] = None, allow_duplicates: bool = False) -> None:
        """Initializes a WebsitePool

        Parameters
        ----------
        name : str, optional
            The name of the WebsitePool, by default None
        allow_duplicates : bool
            Whether to allow duplicate websites in the pool
            or don't, by default False
        """

        self.__sites            = list()
        self.__allow_duplicates = allow_duplicates

        self.set_name(name)

        for site in sites:
            self.add(site)

    def __str__(self) -> str:
        return f"<{self.__class__.__qualname__}(name=\"{self.__name}\", websites={len(self)})>"

    def __len__(self) -> int:
        return len(self.__sites)

    def __iter__(self) -> Generator[Website, None, None]:
        yield from self.__sites

    def __contains__(self, obj: Any) -> bool:
        return isinstance(obj, Website) and any(map(lambda w: w == obj, self))

    def __copy__(self) -> WebsitePool:
        pool = self.__class__.__new__(self.__class__)
        pool.__dict__.update(self.__dict__)

        return pool

    def __deepcopy__(self, memo: Dict[int, Any]) -> WebsitePool:
        pool = self.__class__.__new__(self.__class__)

        memo[id(self)] = pool

        for k, v in self.__dict__.items():
            setattr(pool, k, copy.deepcopy(v, memo))

        return pool

    @property
    def sites(self) -> Tuple[Website]:
        return tuple(self.__sites)

    @property
    def name(self) -> Optional[str]:
        return self.__name

    @property
    def results(self) -> Tuple[Result]:
        return tuple([site.result for site in self if site.result])

    @property
    def is_empty(self) -> bool:
        return not bool(self)

    def set_name(self, name: Optional[str]) -> None:
        """Sets the name for the pool

        Parameters
        ----------
        name : str
            Name for the pool

        Raises
        ------
        TypeError
            name is not type 'str'
        """

        if not isinstance(name, str):
            raise TypeError(f"Expected type 'str' instead of type '{type(name).__qualname__}'")

        self.__name = name

    def set_username(self, username: Optional[str]) -> None:
        """Sets the username for every website within the pool

        Parameters
        ----------
        username : str
            The username to set for every website

        Raises
        ------
        TypeError
            username is not type 'str'
        """

        if not isinstance(username, str):
            raise TypeError(f"Expected type 'str' instead of type '{type(username).__qualname__}'")

        for site in self.sites:
            site.set_username(username)

    def add(self, website: Website) -> None:
        """Adds a website to the pool

        Parameters
        ----------
        website : tracer.Website
            The website to add to the pool

        Raises
        ------
        TypeError
            website is not type 'tracer.Website'
        """

        if not isinstance(website, Website):
            raise TypeError(f"Expected type 'tracer.Website' instead of type '{type(website).__qualname__}'")

        if not self.__allow_duplicates and website in self:
            return None

        self.__sites.append(website)

    def extend(self, pool, _deepcopy: bool = True) -> None:
        """Adds sites from another pool to the own pool

        Parameters
        ----------
        pool : tracer.WebsitePool
            The pool from which to take the sites
        _deepcopy : bool
            Whether to generate copies of the sites and
            add these or add the original sites, by
            default True

        Raises
        ------
        TypeError
            pool is not type 'tracer.WebsitePool'
        """

        if not isinstance(pool, self.__class__):
            raise TypeError(f"Expected type 'tracer.{self.__class__.__qualname__}' instead of type '{type(pool).__qualname__}'")

        for site in pool:
            self.add(copy.deepcopy(site) if _deepcopy else site)

    def remove(self, where: Callable[[Website], bool]) -> None:
        """Removes websites from the pool

        Parameters
        ----------
        where : Callable[[Website], bool]
            A callable which takes in a website object as parameter
            and returns a bool. If `True` is returned, then the
            website will be removed.
        """

        self.__sites = list(filter(lambda w: not where(w), self.sites))

    def get(self, where: Callable[[Website], bool]) -> Tuple[Website]:
        """Retrieves websites from the pool

        Parameters
        ----------
        where : Callable[[Website], bool]
            A callable which takes in a website object as parameter
            and returns a bool. If `True` is returned, then the
            websites will be added to the return tuple.

        Returns
        -------
        Tuple[Website]
            Tuple of websites that were considered True by the
            callable
        """

        return tuple(filter(where, self))

    def get_by_name(self, name: str) -> Optional[Website]:
        """Retrieves a website by its name

        Parameters
        ----------
        name : str
            The name of the website to retrieve

        Returns
        -------
        Optional[Website]
            Either the website object or `None` if not
            found
        """

        result = self.get(lambda w: w.name == name)

        return result[0] if result else None

    async def start_requests(self, session: ClientSession, timeout: Optional[float] = None) -> AsyncGenerator[Result, None]:
        """Prepares and handles all requests

        Calls `send_request` of every tracer.Website object in the pool and
        returns an AsyncGenerator yielding the results of these
        requests when available.

        Parameters
        ----------
        session : aiohttp.ClientSession
            A session object which gets used to make the
            requests.
        timeout : Union[int, float], optional
            Represents the time each request has before a
            TimeoutError occurs.

        Returns
        -------
        AsyncGenerator[Result, None]
            Yields the results of the requests when available.

        Yields
        ------
        tracer.Result
            The representation of the result of a request

        Example
        -------
        >>> results = pool.start_requests(...)

        >>> async for result in results:

        >>>    print(result.url)
        """

        results = asyncio.Queue()

        requests = [site.send_request(session, timeout, callback=results.put) for site in self]

        requests = asyncio.gather(*requests)

        while not (results.empty() and requests.done()):
            try:
                yield await asyncio.wait_for(results.get(), timeout=0.25)
            except Exception:
                """Forces recheck of the loop condition
                """

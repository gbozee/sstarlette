import typing
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse, RedirectResponse


class SResult:
    def __init__(
        self,
        errors: dict = None,
        data: dict = None,
        task: typing.List[typing.Any] = None,
    ):
        self.errors = errors
        self.data = data
        self.task = task

    def as_dict(self, status_code, tasks=None):
        if self.errors:
            response = {"status": False, **self.errors}
        else:
            response = {"status": True}
        if self.data:
            response.update(data=self.data)
        return dict(data=response, status_code=status_code, tasks=tasks)


class DBAbstraction:

    async def connect(self) -> bool:
        raise NotImplementedError

    async def disconnect(self):
        raise NotImplementedError

    def track(self, *args, **kwargs):
        pass

    def json_response(
        self,
        data,
        status_code: int = 200,
        tasks: BackgroundTasks = None,
        redirect=False,
        **kwargs,
    ) -> typing.Union[JSONResponse, RedirectResponse]:
        if redirect:
            return RedirectResponse(url=data, status_code=status_code)
        return JSONResponse(data, status_code=status_code, background=tasks)

    async def build_response(
        self,
        coroutine: typing.Awaitable,
        status_code: int = 400,
        redirect=False,
        redirect_key=None,
        **kwargs,
    ) -> typing.Union[JSONResponse, RedirectResponse]:

        result: SResult = await coroutine
        tasks = BackgroundTasks()
        if result.errors:
            return self.json_response(**result.as_dict(400, tasks=tasks), **kwargs)
        if result.task:
            for i in result.task:
                if type(i) in [list, tuple]:
                    try:
                        dict_index = [type(o) for o in i].index(dict)
                        args_props = i
                        if dict_index:
                            kwarg_props = i[dict_index]
                            args_props = i[0:dict_index]
                        tasks.add_task(*args_props, **kwarg_props)
                    except ValueError:
                        tasks.add_task(*i)
                else:
                    tasks.add_task(i)
        if redirect and redirect_key and result.data:
            redirect_url = result.data.get(redirect_key)
            return self.json_response(
                redirect_url, redirect=True, status_code=301, **kwargs
            )
        return self.json_response(**result.as_dict(200, tasks=tasks), **kwargs)


import sanic.request
import sanic.response

from .ElcobusMessage.ElcobusFrame import ElcobusMessage
from .ElcobusMessage._registry import find_field
from .ElcobusProtocol import ElcobusHttpProtocol


my_source = 0x01


def add_routes(app: sanic.Sanic):
    @app.get('/boiler_temperature')
    async def boiler_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x0d,
            field=find_field('boiler temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/boiler_set_temperature')
    async def boiler_set_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x0d,
            field=find_field('boiler set temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/boiler_return_temperature')
    async def boiler_return_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x11,
            field=find_field('boiler return temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/outdoor_temperature')
    async def outdoor_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x05,
            field=find_field('outdoor temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/tap_water_temperature')
    async def tap_water_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x31,
            field=find_field('tap water temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/tap_water_set_temperature')
    async def tap_water_set_temperature(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x31,
            field=find_field('tap water set temperature'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.temperature)

    @app.get('/burner_modulation')
    async def burner_modulation(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x11,
            field=find_field('burner modulation'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.percent)

    @app.get('/pump_modulation')
    async def pump_modulation(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x05,
            field=find_field('pump modulation'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.percent)

    @app.get('/pressure')
    async def presure(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x11,
            field=find_field('pressure'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.pressure)

    @app.get('/status')
    async def status(request: sanic.request) -> sanic.response:
        bus = ElcobusHttpProtocol(request)
        msg = ElcobusMessage(
            source_address=my_source, destination_address=0x00,
            message_type=ElcobusMessage.MessageType.Get,
            logical_source=0x3d, logical_destination=0x09,
            field=find_field('status'),
        )
        response = await bus.query(msg)
        return sanic.response.json(response.data.status)

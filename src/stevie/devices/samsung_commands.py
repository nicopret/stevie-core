"""Samsung's implemented command interface, not per-device capability evidence."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from stevie.devices.commands import Command, CommandArgument, CommandDefinition, InvalidCommandArgumentsError

# Matches Stevie-Explorer's devices/samsung/keys.py catalogue. No power keys.
REMOTE_KEYS = frozenset({
    'KEY_HOME', 'KEY_RETURN', 'KEY_ENTER', 'KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT',
    'KEY_VOLUP', 'KEY_VOLDOWN', 'KEY_MUTE', 'KEY_CHUP', 'KEY_CHDOWN', 'KEY_PLAY',
    'KEY_PAUSE', 'KEY_STOP', 'KEY_FF', 'KEY_REWIND', 'KEY_SOURCE', 'KEY_GUIDE', 'KEY_INFO',
    *(f'KEY_{number}' for number in range(10)),
})


class NoArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


class KeyArguments(NoArguments):
    key: str = Field(min_length=1)


class ChannelArguments(NoArguments):
    channel: StrictInt = Field(ge=0)


COMMANDS = {
    Command.KEY: ('Remote Key', KeyArguments),
    Command.HOME: ('Home', NoArguments),
    Command.BACK: ('Back', NoArguments),
    Command.VOLUME_UP: ('Volume Up', NoArguments),
    Command.VOLUME_DOWN: ('Volume Down', NoArguments),
    Command.MUTE: ('Mute', NoArguments),
    Command.CHANNEL_UP: ('Channel Up', NoArguments),
    Command.CHANNEL_DOWN: ('Channel Down', NoArguments),
    Command.CHANNEL_SELECT: ('Select Channel', ChannelArguments),
}


def catalogue() -> list[CommandDefinition]:
    return [CommandDefinition(name=command, display_name=label, arguments=[
        CommandArgument(name=name, type='integer' if name == 'channel' else 'string')
        for name in model.model_fields
    ]) for command, (label, model) in COMMANDS.items()]


def validate_arguments(command: Command, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = COMMANDS[command][1].model_validate(arguments)
    except ValidationError:
        raise InvalidCommandArgumentsError('Invalid command arguments') from None
    if isinstance(parsed, KeyArguments) and parsed.key not in REMOTE_KEYS:
        raise InvalidCommandArgumentsError('Key is not in the allowed remote-key catalogue')
    return parsed.model_dump()

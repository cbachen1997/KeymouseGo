from abc import ABCMeta, abstractmethod
from typing import Dict, Any
import math
import json5


class JsonObject:
    def __init__(self, content: Dict[str, Any]):
        self.content = content
        self.next_object = None
        self.next_object_if_false = None


def read_script(path):
    try:
        with open(path, encoding='utf-8-sig') as stream:
            return json5.load(stream)
    except UnicodeDecodeError:
        with open(path, encoding='gbk') as stream:
            return json5.load(stream)


class Parser(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def parse(script_path, *args):
        pass


class ScriptParser(Parser):
    @staticmethod
    def parse(script_path, *args):
        return ScriptParser.from_content(read_script(script_path))

    @staticmethod
    def from_content(content):
        if not isinstance(content, dict) or not isinstance(content.get('scripts'), list):
            raise ValueError('Script must contain a scripts array')
        if not content['scripts']:
            raise ValueError('Script contains no actions')
        labels, pending = {}, {}
        head = ScriptParser.link_objects(content['scripts'], None, labels, pending)
        for node, label in pending.items():
            if label not in labels:
                raise ValueError(f'Unknown label: {label}')
            node.next_object = labels[label]
        return head

    @staticmethod
    def link_objects(objects, target_object, label_maps, pending_dict):
        if not isinstance(objects, list):
            raise ValueError('Action sequence must be an array')
        for index in range(len(objects) - 1, -1, -1):
            original = objects[index]
            if not isinstance(original, dict):
                raise ValueError(f'Action {index + 1} must be an object')
            content = dict(original)
            node = JsonObject(content)
            label = content.get('label')
            if label is not None:
                if label in label_maps:
                    raise ValueError(f'Duplicate label: {label}')
                label_maps[label] = node
            kind = content.get('type')
            node.next_object = target_object
            if kind == 'event':
                validate_event(content, index + 1)
            elif kind == 'sequence':
                content['events'] = ScriptParser.link_objects(content['events'], None, label_maps, pending_dict)
                content.setdefault('attach', [])
            elif kind == 'if':
                if not isinstance(content.get('judge'), str):
                    raise ValueError('Conditional action requires a judge function')
                node.next_object = ScriptParser.link_objects(content.get('do', []), target_object, label_maps, pending_dict)
                node.next_object_if_false = ScriptParser.link_objects(content.get('else', []), target_object, label_maps, pending_dict)
            elif kind == 'goto':
                pending_dict[node] = content['tolabel']
            elif kind == 'subroutine':
                if not isinstance(content.get('path'), list) or not content['path'] or not all(isinstance(p, str) for p in content['path']):
                    raise ValueError('Subroutine path must be a nonempty array of filenames')
            elif kind != 'custom':
                raise ValueError(f'Action {index + 1}: unknown type {kind!r}')
            target_object = node
        return target_object


def validate_event(content, index):
    prefix = f'Action {index}'
    delay = content.get('delay')
    if not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
        raise ValueError(f'{prefix}: delay must be a nonnegative number')
    kind, action, name = content.get('event_type'), content.get('action'), content.get('action_type')
    if kind == 'EK':
        valid = isinstance(action, (list, tuple)) and len(action) == 3 and isinstance(action[0], int) and isinstance(action[1], str) and name in ('key down', 'key up')
    elif kind == 'EM':
        names = ['mouse move', 'mouse wheel up', 'mouse wheel down'] + [f'mouse {button} {direction}' for button in ('left', 'right', 'middle', 'x1', 'x2') for direction in ('down', 'up')]
        valid = isinstance(action, (list, tuple)) and len(action) == 2 and name in names
    elif kind == 'EX':
        valid = name == 'input' and isinstance(action, str)
    else:
        valid = False
    if not valid:
        raise ValueError(f'{prefix}: invalid {kind!r} event')


class LegacyParser(Parser):
    @staticmethod
    def parse(script_path, *args):
        return LegacyParser.from_content(read_script(script_path))

    @staticmethod
    def from_content(content):
        if not isinstance(content, list):
            raise ValueError('Legacy script must be an array')
        events = []
        for index, value in enumerate(content, 1):
            if not isinstance(value, list) or len(value) != 4:
                raise ValueError(f'Legacy action {index}: expected four fields')
            events.append(dict(delay=value[0], event_type=value[1].upper(), action_type=value[2].lower(), action=value[3], type='event'))
        return ScriptParser.from_content({'scripts': events})


def parse_script(path):
    content = read_script(path)
    return LegacyParser.from_content(content) if isinstance(content, list) else ScriptParser.from_content(content)

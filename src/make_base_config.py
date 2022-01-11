import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Generator, Union

import yaml
from jinja2 import Environment, FileSystemLoader


def resource_path(*args) -> Path:
    base_path = None
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys.argv[0]).absolute().parent
    else:
        base_path = Path.cwd()
    return base_path.joinpath(*args)


def set_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', metavar='<Config path>', help='Configファイルを指定')
    parser.add_argument('-i', '--input', metavar='<Input path>', help='入力データパスを指定')
    parser.add_argument('-m', '--mode', metavar='<Mode>', help='モードを指定')
    return parser


def get_config(config_file: Path) -> Dict[str, Any]:
    with config_file.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def read_content(file: Path, option: Dict[str, Any]) -> str:
    with file.open('r') as f:
        data = f.read()
    start = option.get('start', 0)
    end = option.get('end', None)
    # print(start, repr(end))
    if isinstance(start, str):
        match = re.search(re.compile(start), data)
        start = 0 if match is None else match.start()
    if isinstance(end, str):
        match = re.search(re.compile(end), data)
        end = None if match is None else match.end()
    # print(start, end)
    if end is None:
        return data[start:]
    return data[start:end]


def setup_jinja(template_folder: str = '.', encoding: str = 'utf-8') -> Environment:
    env = Environment(loader=FileSystemLoader(template_folder, encoding=encoding))
    return env


def variables(options: Dict[str, dict], content: str, file: Path) -> Dict[str, str]:
    vars = {
        'filename': file.stem,
        'ext': file.suffix,
        'parent': str(file.parent)
    }
    for name, item in options.items():
        # print(name, item)
        target_type = item.get('target')
        if not target_type:
            continue
        target = ''
        if target_type == 'filepath':
            target = str(file.absolute())
        elif target_type == 'filename':
            target = str(file.name)
        elif target_type == 'content':
            target = content
        pattern = re.compile(item.get('pattern', '.*'), re.MULTILINE)
        result = pattern.match(target)
        if not result:
            continue
        index = item.get('index', None)
        vars[name] = result.group() if index is None else result.group(index)
    return vars


def replace_variables(content: str, vars: Dict[str, str]) -> str:
    for target, newstr in vars.items():
        content = content.replace('${'+target+'}', newstr)
    return content


def make_base(files: Union[Generator, list], preset: Dict[str, Any]) -> None:
    template_data = preset.get('template')
    if not template_data:
        return
    env = setup_jinja(template_data.get('folder'))
    params = dict()
    for file in files:
        file = Path(file)
        content = ''
        if preset.get('read_content'):
            content = read_content(file, preset.get('read_content_options', {'start', 0}))
            params.update({'content': content})
        template = env.get_template(template_data.get('file'))
        vars = variables(preset.get('variables', {}), content, file)
        print(vars)
        params.update({'additional_params': preset.get('additional_params')})
        params.update({'variables': vars})
        print(params)
        render = template.render(params)
        save_path = resource_path(replace_variables(preset.get('output', 'output/{filename}_make.{ext}'), vars))
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open('w', encoding='utf-8') as f:
            f.write(render)


if __name__ == '__main__':
    parser = set_parser()
    args = parser.parse_args()

    config = get_config(resource_path('config.yaml') if args.config is None else resource_path(args.config))

    if not config or config.get('presets') is None:
        sys.exit(1)

    presets = {item.get('mode_flag'): item for item in config.get('presets', {}) if item.get('mode_flag')}

    print('Presets:')
    [print(f'  {key}: {val.get("name")}') for key, val in presets.items()]

    mode_flags = input('Mode >>')
    data_path = Path(input('Path >>')) if args.input is None else Path(args.input)

    if data_path.is_dir():
        for mode in mode_flags:
            preset = presets.get(mode)
            if not preset:
                continue
            print(preset.get('name'))
            files = data_path.glob(preset.get('file_pattern', '*'))
            make_base(files, preset)

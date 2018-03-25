
import textwrap
import csv
import sys

from uuid import UUID
from collections import OrderedDict

import click

from . import cli, get_table_instance, bool2str

@cli.group()
@click.pass_context
def testresult(ctx):
    """Manage test results"""
    ctx.obj['testresult_url'] = '{url}/api/v2/testresults'.format(**ctx.obj)


@testresult.command('list')
@click.option('--collection', type=str, help="filter by collection")
@click.option('--test', type=str, help="filter by test ('GW100, 'deltatest', ..)")
@click.option('--structure', type=str, help="filter by structure ('GW100 Hydrogen peroxide', 'deltatest_H_1.00', ..)")
@click.option('--basis_set_family', type=str, help="filter by basis set family")
@click.option('--data-checks', type=(str, bool), multiple=True,
              help="filter by succeeded/failed check (results without the given check will be filtered out)")
@click.option('--data-element', type=str, help="filter by element (only deltatest results)")
@click.option('--hide-tags', type=str, multiple=True,
              help="hide calcs with the given tag(s), if not specified, server default is used")
@click.option('--csv-output', is_flag=True,
              default=False, show_default=True,
              help="output in CSV format")
@click.option('--header/--no-header', default=True, show_default=True, help="print header")
@click.pass_context
def testresult_list(ctx, csv_output, header, **filters):
    """
    List test results
    """

    # filter out filters not specified
    params = {k: v for k, v in filters.items() if v}
    params['data'] = {}

    if 'data_checks' in params:
        for k, v in params.pop('data_checks'):
            params['data.checks.' + k] = v

    if 'data_element' in params:
        params['data.element'] = params.pop('data_element')

    req = ctx.obj['session'].get(ctx.obj['testresult_url'], params=params)
    req.raise_for_status()
    testresults = req.json()

    header_data = [['id', 'collections', 'test', 'calc ID: structure, code']]
    if not header:
        header_data = []

    table_data = []

    def coll_format(coll):
        marker = ""
        if coll['autogenerated_for']:
            marker = ">"
        return "{:1}{}".format(marker, coll['name'][:30] + '..' if len(coll['name']) > 32 else coll['name'])

    for tresult in testresults:
        table_data.append((
            tresult['id'],
            '\n'.join(sorted([coll_format(c) for c in tresult['collections']], reverse=True)),
            tresult['test'],
            '\n'.join("{id}: {structure}, {code}".format(**c) for c in sorted(tresult['calculations'], key=lambda c: c['structure']))
            ))

    if csv_output:
        writer = csv.writer(sys.stdout, lineterminator='\n')
        writer.writerows([s.replace('\n', '\\n') for s in row] for row in header_data + table_data)
    else:
        table_instance = get_table_instance(header_data + table_data, header)
        click.echo(table_instance.table)

    click.echo(">: mark for the primary/automatically generated test result set, corresponds to a calculation set", err=True)


@testresult.command('tag')
@click.argument('tag', type=str, required=True)
@click.argument('ids', type=UUID, nargs=-1, required=True)
@click.option('--reset-tags/--no-reset-tags', help="completely reset tags before setting new one")
@click.pass_context
def testresult_tag(ctx, tag, ids, reset_tags):
    """
    Tag test results
    """

    for trid in ids:
        click.echo("Setting tag '{}' for test result {}".format(tag, trid), err=True)
        req = ctx.obj['session'].get(ctx.obj['testresult_url'] + '/{}'.format(trid))
        req.raise_for_status()
        tresult = req.json()

        metadata = tresult['metadata']

        if not 'tags' in metadata or reset_tags:
            metadata['tags'] = []

        metadata['tags'].append(tag)

        req = ctx.obj['session'].patch(tresult['_links']['self'], json={'metadata': metadata})
        req.raise_for_status()


@testresult.command('generate-results')
@click.option('--update/--no-update', default=False, show_default=True,
              help="Rewrite the testresult even if already present")
@click.option('--id', 'ids', type=UUID, required=False, multiple=True,
              help="restrict action to specified testresult")
@click.pass_context
def testresult_generate_results(ctx, update, ids):
    """Read results from calculations and generate respective test results"""

    if ids:
        for tid in ids:
            click.echo("Trigger test result (re-)generation for test result {}".format(tid))
            req = ctx.obj['session'].post(ctx.obj['testresult_url'] + '/{}/action'.format(tid),
                                          json={'generate': {'update': update}})
            req.raise_for_status()
    else:
        click.echo("Trigger test result (re-)generation for all calculations, resp. test results")
        req = ctx.obj['session'].post(ctx.obj['testresult_url'] + '/action',
                                      json={'generate': {'update': update}})
        req.raise_for_status()

    # TODO: implement result parsing and waiting for finish


@cli.group()
@click.pass_context
def trcollections(ctx):
    """Manage test result collectionss"""
    ctx.obj['trcollections_url'] = '{url}/api/v2/testresultcollections'.format(**ctx.obj)


@trcollections.command('list')
@click.pass_context
def trcollections_list(ctx):
    """
    List test result collections
    """

    req = ctx.obj['session'].get(ctx.obj['trcollections_url'])
    req.raise_for_status()
    trcolls = req.json()

    table_data = [
        ['id', 'name', 'number of results', 'description'],
        ]

    for trcoll in trcolls:
        table_data.append([
            trcoll['id'],
            "\n".join(textwrap.wrap(trcoll['name'], width=20)),
            trcoll['testresult_count'],
            "\n".join(textwrap.wrap(trcoll['desc'], width=40)),
            ])

    table_instance = get_table_instance(table_data)
    click.echo(table_instance.table)


@trcollections.command('show')
@click.argument('id', type=UUID, required=True)
@click.option('--extended-info/--no-extended-info', default=False, show_default=True,
              help="Whether to fetch and show extended calculation info")
@click.pass_context
def trcollections_show(ctx, extended_info, id):
    """
    Show details for the specified collection
    """

    req = ctx.obj['session'].get(ctx.obj['trcollections_url'] + '/%s' % id)
    req.raise_for_status()
    trcoll = req.json()

    click.echo("Name: {name}".format(**trcoll))
    click.echo("Description:\n{desc}\n".format(**trcoll))

    click.echo("Testresults ({testresult_count}):\n".format(**trcoll))

    table_data = [
        ['id', 'test', 'data', 'data:checks'],
        ]

    if extended_info:
        table_data[0].append("calc collections")
        table_data[0].append("calc ids")

    for tr in trcoll['testresults']:
        entry = [tr['id'], tr['test']]

        tdata = tr['data']
        if 'element' in tdata:
            entry.append("element: {element}".format(**tdata))
        else:
            entry.append("(unavail.)")

        if 'checks' in tdata:
            entry.append(", ".join(["{}: {}".format(k, bool2str(v)) for k, v in tdata['checks'].items()]))
        else:
            entry.append("")

        if extended_info:
            req = ctx.obj['session'].get(tr['_links']['self'])
            req.raise_for_status()
            fulltr = req.json()

            calcs = fulltr['calculations']

            entry.append("\n".join(set(calc['collection'] for calc in fulltr['calculations'])))
            entry.append("\n".join(calc['id'] for calc in fulltr['calculations']))


        table_data.append(entry)

    table_instance = get_table_instance(table_data)
    click.echo(table_instance.table)


@trcollections.command('create')
@click.option('--name', type=str, required=True, prompt=True)
@click.option('--desc', type=str, required=True, prompt=True)
@click.option('--copy-from', type=UUID, required=False,
              help="copy test results from another collection")
@click.option('--copy-from-exclude', type=UUID, required=False, multiple=True,
              help="exclude the specified test result(s) from the collection to copy from")
@click.option('--include', type=UUID, required=False, multiple=True,
              help="include the specified test result(s) in the new collection")
@click.pass_context
def trcollections_create(ctx, name, desc, copy_from, copy_from_exclude, include):
    """
    Create a test result collection
    """

    # populate the results to be added by the include list,
    # converting the UUID objects back to strings while at it
    results = [str(i) for i in include] if include else []

    if copy_from:
        req = ctx.obj['session'].get(ctx.obj['trcollections_url'] + '/%s' % copy_from)
        req.raise_for_status()
        trcoll = req.json()

        excludes = [str(i) for i in copy_from_exclude] if copy_from_exclude else []
        results += [tr['id'] for tr in trcoll['testresults'] if tr['id'] not in excludes]

    payload = {
        'name': name,
        'desc': desc,
        'testresults': results,
        }

    req = ctx.obj['session'].post(ctx.obj['trcollections_url'], json=payload)
    req.raise_for_status()
    trcoll = req.json()

    click.echo("done, the assigned ID for the new collection: {id}".format(**trcoll))


@trcollections.command('delete')
@click.argument('id', type=UUID, required=True)
@click.pass_context
def trcollections_delete(ctx, id):
    """
    Delete a test result collection (does not remove test results)
    """

    req = ctx.obj['session'].delete(ctx.obj['trcollections_url'] + '/%s' % id)
    req.raise_for_status()

    click.echo("done")

"""Record otherwise invisible windowed-Tk callback failures beside the save."""
import datetime
import json
import traceback


def install_callback_log(app):
    def report(kind, value, trace):
        runtime = app.runtime
        context = {'time': datetime.datetime.now().isoformat(timespec='seconds'),
                   'map': app.map_id, 'task': app.state.main_task,
                   'event': runtime.file, 'index': runtime.index,
                   'pending': runtime.pending.kind if runtime.pending else None,
                   'ui': app.ui_parameters.get('uiid')}
        try:
            folder = app.save_path.parent
            folder.mkdir(parents=True, exist_ok=True)
            path = folder/'game-errors.log'
            if path.exists() and path.stat().st_size > 2*1024*1024:
                path.replace(folder/'game-errors.previous.log')
            with path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(context, ensure_ascii=False)+'\n')
                stream.write(''.join(traceback.format_exception(kind, value, trace))+'\n')
        except OSError:
            pass
    app.root.report_callback_exception = report
    app.record_callback_error = report

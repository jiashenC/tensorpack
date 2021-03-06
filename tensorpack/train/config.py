# -*- coding: utf-8 -*-
# File: config.py
# Author: Yuxin Wu <ppwwyyxxc@gmail.com>

from ..callbacks import (
    Callbacks, MovingAverageSummary,
    ProgressBar, MergeAllSummaries,
    TFSummaryWriter, JSONWriter, ScalarPrinter, RunUpdateOps)
from ..dataflow.base import DataFlow
from ..models import ModelDesc
from ..utils import logger
from ..utils.develop import log_deprecated
from ..tfutils import (JustCurrentSession,
                       get_default_sess_config, SessionInit)
from ..tfutils.sesscreate import NewSessionCreator
from .input_source import InputSource

__all__ = ['TrainConfig']


class TrainConfig(object):
    """
    Config for trainer.
    """

    def __init__(self,
                 dataflow=None, data=None,
                 model=None,
                 callbacks=None, extra_callbacks=None,
                 monitors=None,
                 session_creator=None, session_config=None, session_init=None,
                 starting_epoch=1, steps_per_epoch=None, max_epoch=99999,
                 nr_tower=1, tower=None, predict_tower=[0],
                 **kwargs):
        """
        Args:
            dataflow (DataFlow): the dataflow to train.
            data (InputSource): an `InputSource` instance. Only one of ``dataflow``
                or ``data`` has to be present.
            model (ModelDesc): the model to train.
            callbacks (list): a list of :class:`Callback` to perform during training.
            extra_callbacks (list): the same as ``callbacks``. This argument
                is only used to provide the defaults. The defaults are
                ``[MovingAverageSummary(), ProgressBar(), MergeAllSummaries(), RunUpdateOps()]``. The list of
                callbacks that will be used in the end are ``callbacks + extra_callbacks``.
            monitors (list): a list of :class:`TrainingMonitor`.
                Defaults to ``[TFSummaryWriter(), JSONWriter(), ScalarPrinter()]``.
            session_creator (tf.train.SessionCreator): Defaults to :class:`sesscreate.NewSessionCreator()`
                with the config returned by :func:`tfutils.get_default_sess_config()`.
            session_config (tf.ConfigProto): when session_creator is None, use this to create the session.
            session_init (SessionInit): how to initialize variables of a session. Defaults to do nothing.
            starting_epoch (int): The index of the first epoch.
            steps_per_epoch (int): the number of steps (defined by :meth:`Trainer.run_step`) to run in each epoch.
                Defaults to the input data size.
            max_epoch (int): maximum number of epoch to run training.
            nr_tower (int): number of training towers.
            tower (list of int): list of training towers in relative id.
            predict_tower (list of int): list of prediction towers in their relative gpu id. Use -1 for cpu.
        """

        # TODO type checker decorator
        def assert_type(v, tp):
            assert isinstance(v, tp), v.__class__

        # process data
        if 'dataset' in kwargs:
            dataflow = kwargs.pop('dataset')
            log_deprecated("TrainConfig.dataset", "Use TrainConfig.dataflow instead.")
        if dataflow is not None:
            assert data is None, "dataflow and data cannot be both presented in TrainConfig!"
            self.dataflow = dataflow
            assert_type(self.dataflow, DataFlow)
            self.data = None
        else:
            self.data = data
            assert_type(self.data, InputSource)
            self.dataflow = None

        if callbacks is None:
            callbacks = []
        assert not isinstance(callbacks, Callbacks), \
            "TrainConfig(callbacks=Callbacks([...]))" \
            "Change the argument 'callbacks=' to a *list* of callbacks without StatPrinter()."
        assert_type(callbacks, list)
        if extra_callbacks is None:
            extra_callbacks = [
                MovingAverageSummary(),
                ProgressBar(),
                MergeAllSummaries(),
                RunUpdateOps()]
        self._callbacks = callbacks + extra_callbacks
        assert_type(self._callbacks, list)

        if monitors is None:
            monitors = [TFSummaryWriter(), JSONWriter(), ScalarPrinter()]
        self.monitors = monitors

        self.model = model
        assert_type(self.model, ModelDesc)

        if session_init is None:
            session_init = JustCurrentSession()
        self.session_init = session_init
        assert_type(self.session_init, SessionInit)

        if session_creator is None:
            if session_config is not None:
                self.session_creator = NewSessionCreator(config=session_config)
            else:
                self.session_creator = NewSessionCreator(config=get_default_sess_config())
        else:
            self.session_creator = session_creator
            assert session_config is None, "Cannot set both session_creator and session_config!"
        self.session_config = session_config

        if steps_per_epoch is None:
            steps_per_epoch = kwargs.pop('step_per_epoch', None)
            if steps_per_epoch is not None:
                log_deprecated("step_per_epoch", "Use steps_per_epoch instead!", "2017-03-27")
        if steps_per_epoch is None:
            try:
                if dataflow is not None:
                    steps_per_epoch = self.dataflow.size()
                else:
                    steps_per_epoch = self.data.size()
            except NotImplementedError:
                logger.exception("You must set `steps_per_epoch` if dataset.size() is not implemented.")
        else:
            steps_per_epoch = int(steps_per_epoch)
        self.steps_per_epoch = steps_per_epoch

        self.starting_epoch = int(starting_epoch)
        self.max_epoch = int(max_epoch)
        assert self.steps_per_epoch >= 0 and self.max_epoch > 0

        self.nr_tower = nr_tower
        if tower is not None:
            assert self.nr_tower == 1, "Cannot set both nr_tower and tower in TrainConfig!"
            self.tower = tower

        self.predict_tower = predict_tower
        if isinstance(self.predict_tower, int):
            self.predict_tower = [self.predict_tower]
        assert len(set(self.predict_tower)) == len(self.predict_tower), \
            "Cannot have duplicated predict_tower!"

        assert 'optimizer' not in kwargs, \
            "TrainConfig(optimizer=...) was already deprecated! " \
            "Use ModelDesc._get_optimizer() instead."
        assert len(kwargs) == 0, 'Unknown arguments: {}'.format(str(kwargs.keys()))

    @property
    def nr_tower(self):
        return len(self.tower)

    @nr_tower.setter
    def nr_tower(self, value):
        self.tower = list(range(value))

    @property
    def callbacks(self):        # disable setter
        return self._callbacks

# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES, ETH Zurich, and University of Toronto
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import re
import torch
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

from omni.isaac.core.utils.types import ArticulationActions

if TYPE_CHECKING:
    from .actuator_cfg import ActuatorBaseCfg


class ActuatorBase(ABC):
    """Base class for applying actuator models over a collection of actuated joints in an articulation.

    The default actuator for applying the same actuator model over a collection of actuated joints in
    an articulation.

    The joint names are specified in the configuration through a list of regular expressions. The regular
    expressions are matched against the joint names in the articulation. The first match is used to determine
    the joint indices in the articulation.

    In the default actuator, no constraints or formatting is performed over the input actions. Thus, the
    input actions are directly used to compute the joint actions in the :meth:`compute`.
    """

    computed_effort: torch.Tensor
    """The computed effort for the actuator group. Shape is ``(num_envs, num_joints)``."""
    applied_effort: torch.Tensor
    """The applied effort for the actuator group. Shape is ``(num_envs, num_joints)``."""
    effort_limit: float = torch.inf
    """The effort limit for the actuator group. Shape is ``(num_envs, num_joints)``."""
    velocity_limit: float = torch.inf
    """The velocity limit for the actuator group. Shape is ``(num_envs, num_joints)``."""
    stiffness: torch.Tensor
    """The stiffness (P gain) of the PD controller. Shape is ``(num_envs, num_joints)``."""
    damping: torch.Tensor
    """The damping (D gain) of the PD controller. Shape is ``(num_envs, num_joints)``."""

    def __init__(
        self, cfg: ActuatorBaseCfg, dof_names: list[str], dof_ids: list[int] | Ellipsis, num_envs: int, device: str
    ):
        """Initialize the actuator.

        Args:
            cfg (ActuatorBaseCfg): The configuration of the actuator model.
            dof_names (list[str]): The joint names in the articulation.
            dof_ids (list[int] | Ellipsis): The joint indices in the articulation.
            num_envs (int): Number of articulations in the view.
            device (str): Device used for processing.
        """
        # save parameters
        self.cfg = cfg
        self._num_envs = num_envs
        self._device = device
        self._dof_names = dof_names
        self._dof_indices = dof_ids

        # create commands buffers for allocation
        self.computed_effort = torch.zeros(self._num_envs, self.num_joints, device=self._device)
        self.applied_effort = torch.zeros_like(self.computed_effort)
        self.stiffness = torch.zeros_like(self.computed_effort)
        self.damping = torch.zeros_like(self.computed_effort)

        # parse joint limits
        if self.cfg.effort_limit is not None:
            self.effort_limit = self.cfg.effort_limit
        if self.cfg.velocity_limit is not None:
            self.velocity_limit = self.cfg.velocity_limit
        # parse joint stiffness and damping
        for index, dof_name in enumerate(self.dof_names):
            # -- stiffness
            if self.cfg.stiffness is not None:
                for re_key, value in self.cfg.stiffness.items():
                    if re.fullmatch(re_key, dof_name):
                        if value is not None:
                            self.stiffness[:, index] = value
            # -- damping
            if self.cfg.damping is not None:
                for re_key, value in self.cfg.damping.items():
                    if re.fullmatch(re_key, dof_name):
                        if value is not None:
                            self.damping[:, index] = value

    def __str__(self) -> str:
        """A string representation of the actuator group."""
        # resolve joint indices for printing
        dof_indices = self.dof_indices
        if dof_indices is Ellipsis:
            dof_indices = list(range(self.num_joints))
        return (
            f"<class {self.__class__.__name__}> object:\n"
            f"\tNumber of joints      : {self.num_joints}\n"
            f"\tJoint names expression: {self.cfg.dof_names_expr}\n"
            f"\tJoint names           : {self.dof_names}\n"
            f"\tJoint indices         : {dof_indices}\n"
        )

    """
    Properties.
    """

    @property
    def num_joints(self) -> int:
        """Number of actuators in the group."""
        return len(self._dof_names)

    @property
    def dof_names(self) -> list[str]:
        """Articulation's joint names that are part of the group."""
        return self._dof_names

    @property
    def dof_indices(self) -> list[int] | Ellipsis:
        """Articulation's joint indices that are part of the group.

        Note:
            If :obj:`Ellipsis` is returned, then the group contains all the joints in the articulation.
        """
        return self._dof_indices

    """
    Operations.
    """

    @abstractmethod
    def reset(self, env_ids: Sequence[int]):
        """Reset the internals within the group.

        Args:
            env_ids (Sequence[int]): List of environment IDs to reset.
        """
        raise NotImplementedError

    @abstractmethod
    def compute(
        self, control_action: ArticulationActions, dof_pos: torch.Tensor, dof_vel: torch.Tensor
    ) -> ArticulationActions:
        """Process the actuator group actions and compute the articulation actions.

        It computes the articulation actions based on the actuator model type

        Args:
            control_action (ArticulationActions): The joint action instance comprising of the desired joint
                positions, joint velocities and (feed-forward) joint efforts.
            dof_pos (torch.Tensor): The current joint positions of the joints in the group.
                Shape is ``(num_envs, num_joints)``.
            dof_vel (torch.Tensor): The current joint velocities of the joints in the group.
                Shape is ``(num_envs, num_joints)``.

        Returns:
            ArticulationActions: The computed desired joint positions, joint velocities and joint efforts.
        """
        raise NotImplementedError

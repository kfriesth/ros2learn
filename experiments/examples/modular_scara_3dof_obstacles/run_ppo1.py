import numpy as np
import sys

import gym
import gym_gazebo

import tensorflow as tf

import argparse
import copy
import time

from baselines import logger
from baselines.common import set_global_seeds, tf_util as U

from baselines.acktr.acktr_cont import learn
from baselines.agent.utility.general_utils import get_ee_points, get_position
from baselines.ppo1 import mlp_policy, pposgd_simple


env = gym.make('GazeboModularScara3DOF-v3')
initial_observation = env.reset()
print("Initial observation: ", initial_observation)
env.render()
seed = 0

sess = U.make_session(num_cpu=1)
sess.__enter__()
def policy_fn(name, ob_space, ac_space):
    return mlp_policy.MlpPolicy(name=name, ob_space=ob_space, ac_space=ac_space,
    hid_size=64, num_hid_layers=2)
# gym.logger.setLevel(logging.WARN)
# env.randomizeObstacle()
obs = env.reset()
print("Initial obs: ", obs)
# env.seed(seed)
# time.sleep(5)
pi = policy_fn("pi", env.observation_space, env.action_space)
tf.train.Saver().restore(sess, '/home/rkojcev/baseline_networks/GazeboModularScaraStaticObstacle3DOF-v1/ppo/2_1/models/3dof_ppo1_test_H_afterIter_480.model') # for the H
done = False
while True:
    action = pi.act(True, obs)[0]
    obs, reward, done, info = env.step(action)
    print(action)
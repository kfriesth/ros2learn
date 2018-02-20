import argparse
import tensorflow as tf

from mpi4py import MPI
from rl_algs.common import set_global_seeds, tf_util as U
import os.path as osp
import gym, logging
import numpy as np
from collections import deque
from gym import spaces
import rl_algs.common.misc_util
import sys
import shutil
import subprocess
import gym_gazebo
import time

import time
import gym_gazebo

import mlsh_code.rollouts_robotics_mult as rollouts
from mlsh_code.policy_network import Policy
from mlsh_code.subpolicy_network import SubPolicy
from mlsh_code.observation_network import Features
from mlsh_code.learner import Learner
import rl_algs.common.tf_util as U
import pickle

from scipy import interpolate

# here we define the parameters necessary to launch
savename = 'ScaraTest'
replay_bool= 'True'
macro_duration = 5
# num_subs = 4
num_subs = 2
num_rollouts = 2500
warmup_time = 5 #1 # 30
train_time = 2 #2 # 200
force_subpolicy = None
store=True

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

replay = str2bool(replay_bool)
# args.replay = str2bool(args.replay)

RELPATH = osp.join(savename)
LOGDIR = osp.join('/root/results' if sys.platform.startswith('linux') else '/tmp', RELPATH)

def start(callback,session, workerseed, rank, comm):
    env = gym.make('GazeboModularScara3DOF-v3')
    env.init_time(slowness= 2, slowness_unit='sec', reset_jnts=False)
    env.seed(workerseed)
    np.random.seed(workerseed)
    ob_space = env.observation_space
    ac_space = env.action_space
    stochastic= True
    stochastic_subpolicy=False
    #env.init_4dof_robot()


    #env.init_time(6, 'sec')## Set time to 10 seconds
    # num_subs = args.num_subs
    # macro_duration = args.macro_duration
    # num_rollouts = args.num_rollouts
    # warmup_time = args.warmup_time
    # train_time = args.train_time

    # num_batches = 15

    # observation in.
    savedir = " "
    ob = U.get_placeholder(name="ob", dtype=tf.float32, shape=[None, ob_space.shape[0]])
    policy = Policy(name="policy", ob=ob, ac_space=ac_space, hid_size=32, num_hid_layers=2, num_subpolicies=num_subs)
    old_policy = Policy(name="old_policy", ob=ob, ac_space=ac_space, hid_size=32, num_hid_layers=2, num_subpolicies=num_subs)

    sub_policies = [SubPolicy(name="sub_policy_%i" % x, ob=ob, ac_space=ac_space, hid_size=32, num_hid_layers=2) for x in range(num_subs)]
    old_sub_policies = [SubPolicy(name="old_sub_policy_%i" % x, ob=ob, ac_space=ac_space, hid_size=32, num_hid_layers=2) for x in range(num_subs)]

    learner = Learner(env, policy, old_policy, sub_policies, old_sub_policies, comm, clip_param=0.2, entcoeff=0, optim_epochs=10, optim_stepsize=3e-5, optim_batchsize=64)
    rollout = rollouts.traj_segment_generator(policy, sub_policies, env, macro_duration,num_rollouts, replay, savedir,force_subpolicy, stochastic=False)
    #

    callback(session)
    # learner.syncSubpolicies()
    policy.reset()
    # learner.syncMasterPolicies()
    #env.randomizeCorrect()
    #env.randomizeRobot()

    #Uncomment to test with 3Dof robot
    #env.init_3dof_robot()
    # env.realgoal= [0.3325683, 0.0657366, 0.3746] # center of the O
    # env.realgoal= [0.3305805, -0.1326121, 0.3746] # center of the H

    # env.realgoal = [0.3305805, -0.1326121, 0.3746] # center of the H
    # env.realgoal = [0.3305805, -0.0985179, 0.3746] # center of H right
    # env.realgoal = [0.3733744, -0.1646508, 0.3746] # center of H left

    # env.realgoal = [0.3325683, 0.0657366, 0.3746] # center of O
    # env.realgoal = [0.3355224, 0.0344309, 0.3746] # center of O left
    # env.realgoal = [0.3013209, 0.1647450, 0.3746] # S top right
    # env.realgoal = [0.2877867, -0.1005370, 0.3746] # - middle
    # env.realgoal = [0.3349774, 0.1570571, 0.3746] # S center

    # env.realgoal = [0.3341184, 0.0126104, 0.3746] # R middle right
    # env.realgoal = [0.3731659, -0.0065453, 0.3746] # R down right
    env.realgoal = [0.2250708, -0.0422738, 0.3746] # R top left


    shared_goal = comm.bcast(env.realgoal, root=0)
    print("The goal to %s" % (env.realgoal))
    print("which robot? ", env.choose_robot)
    obs=env.reset()
    print("OBS: ", obs)
    t = 0

    # time.sleep(1)
    new_test = True
    file_endeffector = open('end_effector_3dof_mlsh_simulation_stochastic_interp_o.csv', 'w')
    while True:
        # env.init_3dof_robot()
        #print("t", t)
        if t % macro_duration == 0:
            cur_subpolicy, macro_vpred = policy.act(stochastic, obs)

        # if np.random.uniform() < 0.1:
        #         cur_subpolicy = np.random.randint(0, len(sub_policies))
        # print("cur_subpolicy", cur_subpolicy)
        ac, vpred = sub_policies[cur_subpolicy].act(stochastic_subpolicy, obs)

        # # print("obs[0:3]:",obs[0:3])
        # # print("ac:",ac)
        #
        nodes = np.array( [ [obs[0], obs[1], obs[2]], [ac[0], ac[1], ac[2]]] )
        j1 = nodes[:,0]
        j2 = nodes[:,1]
        j3 = nodes[:,2]
        tick,u = interpolate.splprep([j1,j2,j3], k=1)
        j1_new,j2_new, j3_new  = interpolate.splev( np.linspace( 0, 0.07, 10 ), tick,der = 0)


        ac_new = [j1_new[9], j2_new[9], j3_new[9]]
        file_endeffector.write(str(ac[0]) + ", " + str(ac[1]) + ", " + str(ac[2]) + ", " +
                               str(ac_new[0]) + ", " + str(ac_new[1]) + ", " + str(ac_new[2]) + ", " +
                               str(obs[0]) + ", " + str(obs[1]) + ", " + str(obs[2]) +"\n")
        obs, rew, new, info = env.step(ac_new)

        # #no interpolation
        # file_endeffector.write(str(ac[0]) + ", " + str(ac[1]) + ", " + str(ac[2]) + ", " +  str(obs[0]) + ", " + str(obs[1]) + ", " + str(obs[2]) + "\n")
        # obs, rew, new, info = env.step(ac)
        t += 1
    file_endeffector.close()


def callback(session):
    # if MPI.COMM_WORLD.Get_rank()==0:
    #     if it % 2 == 0 and it > 3: # and not replay:
    #         fname = osp.join("savedir/", 'checkpoints', '%.5i'%it)
    #         U.save_state(fname)
    # if it == 0:
    print("CALLBACK")
    # fname = '/tmp/rosrl/mlsh/saved_models/00310'
    #fname = '/tmp/rosrl/GazeboModularScara4and3DOF/saved_models/00310'
    # fname = '/home/rkojcev/baselines_networks/mlsh_params_eval/macro_dur_5_warmup_time_5/00038'
    fname = '/home/rkojcev/baselines_networks/mlsh_params_eval/macro_dur_5_warmup_time_20/saved_models/00048'
    # subvars = []
    # subvars += tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="sub_policy_0")
    # for i in range(num_subs-1):
    #     subvars += tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="sub_policy_%i" % (i))
    #     print("subvars:", subvars)
    # # subvars += tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="sub_policy_%i" % (i))
    # subvars += tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="policy")
    # print([v.name for v in subvars])
    tf.train.Saver().restore(session, fname)
    # U.load_state(fname, subvars)
    # time.sleep(5)
    pass

def load():
    num_timesteps=1e9
    seed = 1401
    rank = MPI.COMM_WORLD.Get_rank()
    sess = U.single_threaded_session()
    sess.__enter__()
    workerseed = seed + 1000 * MPI.COMM_WORLD.Get_rank()
    rank = MPI.COMM_WORLD.Get_rank()
    set_global_seeds(workerseed)

    # if rank != 0:
    #     logger.set_level(logger.DISABLED)
    # logger.log("rank %i" % MPI.COMM_WORLD.Get_rank())

    world_group = MPI.COMM_WORLD.Get_group()
    mygroup = rank % 10
    theta_group = world_group.Incl([x for x in range(MPI.COMM_WORLD.size) if (x % 10 == mygroup)])
    comm = MPI.COMM_WORLD.Create(theta_group)
    comm.Barrier()
    # comm = MPI.COMM_WORLD

    #master_robotics.start(callback, args=args, workerseed=workerseed, rank=rank, comm=comm)
    start(callback,sess, workerseed=workerseed, rank=rank, comm=comm)

def main():
    if MPI.COMM_WORLD.Get_rank() == 0 and osp.exists(LOGDIR):
        shutil.rmtree(LOGDIR)
    MPI.COMM_WORLD.Barrier()
    # with logger.session(dir=LOGDIR):
    load()

if __name__ == '__main__':
    main()
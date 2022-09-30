import numpy as np
import torch


class ReplayMemory(object):

    def __init__(self, STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings):
        self.userDefinedSettings = userDefinedSettings

        self.basicBuffer = BasicMemory(STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings)
        if userDefinedSettings.LSTM_FLAG:
            self.lstmBuffer = LSTMMemory(STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings)
        if userDefinedSettings.DOMAIN_RANDOMIZATION_FLAG:
            self.domainBuffer = DomainMemory(STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings)

    def get_marge(self, agents):
        self.clear()
        for agent in agents:
            self.add_from_other(agent.replay_buffer, clear_buffer_flag=False)

    def clear(self):
        self.basicBuffer.clear()
        if self.userDefinedSettings.LSTM_FLAG:
            self.lstmBuffer.clear()
        if self.userDefinedSettings.DOMAIN_RANDOMIZATION_FLAG:
            self.domainBuffer.clear()

    def add_from_other(self, other_buffer, clear_buffer_flag=False):
        if clear_buffer_flag is True:
            self.clear()

        all_sample = other_buffer.sample(len(other_buffer), sampling_method='all', get_debug_term_flag=True)
        for sample_num in range(len(other_buffer)):
            for step_num in range(all_sample[0].shape[1]):
                state = all_sample[0][sample_num][step_num].cpu().numpy()
                action = all_sample[1][sample_num][step_num].cpu().numpy()
                reward = all_sample[2][sample_num][step_num].cpu().numpy()
                next_state = all_sample[3][sample_num][step_num].cpu().numpy()
                done = all_sample[4][sample_num][step_num].cpu().numpy()
                hidden_in_0 = all_sample[5]['hidden_in'][0][:, sample_num, :].unsqueeze(0)
                hidden_in_1 = all_sample[5]['hidden_in'][1][:, sample_num, :].unsqueeze(0)
                hidden_out_0 = all_sample[5]['hidden_out'][0][:, sample_num, :].unsqueeze(0)
                hidden_out_1 = all_sample[5]['hidden_out'][1][:, sample_num, :].unsqueeze(0)
                last_action = all_sample[5]['last_action'][sample_num][step_num].cpu().numpy()
                lstm_term = {'last_action': last_action,
                             'hidden_in': [hidden_in_0, hidden_in_1],
                             'hidden_out': [hidden_out_0, hidden_out_1]}
                domain_parameter = all_sample[6][sample_num][step_num].cpu().numpy()
                debug_term = all_sample[7][sample_num][step_num].cpu().numpy()
                self.push(state, action, reward, next_state, done, lstm_term=lstm_term,
                          domain_parameter=domain_parameter, debug_term=debug_term,
                          step=step_num)

    def push(self, state, action, reward, next_state, done, lstm_term=None, domain_parameter=None, step=None, debug_term=-1):
        assert step is not None, 'input step number to replay memory push'
        base_term = [step, state, action, reward, next_state, done, debug_term]
        lstm_term = [step, lstm_term]
        domain_term = [step, domain_parameter]

        self.basicBuffer.push(base_term)
        if self.userDefinedSettings.LSTM_FLAG:
            self.lstmBuffer.push(lstm_term)
        if self.userDefinedSettings.DOMAIN_RANDOMIZATION_FLAG:
            self.domainBuffer.push(domain_term)

    def sample(self, batch_size, sampling_method='random', get_debug_term_flag=False):
        if sampling_method == 'random':
            batch_index = np.random.randint(low=0, high=len(self), size=batch_size)
        elif sampling_method == 'last':
            batch_index = np.array(range(len(self) - batch_size, len(self)))
        elif sampling_method == 'all':
            batch_index = range(batch_size)
        else:
            assert False, 'choose  a correct sampling method of replay memory'

        state, action, reward, next_state, done, debug_term = self.basicBuffer.sample(batch_index=batch_index)
        if self.userDefinedSettings.LSTM_FLAG:
            lstm_term = self.lstmBuffer.sample(batch_index=batch_index)
        else:
            lstm_term = None
        if self.userDefinedSettings.DOMAIN_RANDOMIZATION_FLAG:
            domain_parameter = self.domainBuffer.sample(batch_index=batch_index)
        else:
            domain_parameter = None

        if get_debug_term_flag is True:
            return state, action, reward, next_state, done, lstm_term, domain_parameter, debug_term
        else:
            return state, action, reward, next_state, done, lstm_term, domain_parameter

    def __len__(self):
        return len(self.basicBuffer)


class BasicMemory(object):
    def __init__(self, STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings):
        self.userDefinedSettings = userDefinedSettings

        if userDefinedSettings.LSTM_FLAG:
            memory_size = int(userDefinedSettings.memory_size / MAX_EPISODE_LENGTH)
            SEQUENCE_LENGTH = MAX_EPISODE_LENGTH
        else:
            memory_size = int(userDefinedSettings.memory_size)
            SEQUENCE_LENGTH = 1

        if userDefinedSettings.ACTION_DISCRETE_FLAG is True:
            self.action_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[1], userDefinedSettings=userDefinedSettings)
        else:
            self.action_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[ACTION_DIM], userDefinedSettings=userDefinedSettings)
        self.state_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[STATE_DIM], userDefinedSettings=userDefinedSettings)
        self.reward_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[1], userDefinedSettings=userDefinedSettings)
        self.next_state_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[STATE_DIM], userDefinedSettings=userDefinedSettings)
        self.done_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[1], userDefinedSettings=userDefinedSettings)
        self.debug_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[1], userDefinedSettings=userDefinedSettings)  # debug

    def clear(self):
        self.action_buffer.clear()
        self.state_buffer.clear()
        self.reward_buffer.clear()
        self.next_state_buffer.clear()
        self.done_buffer.clear()
        self.debug_buffer.clear()

    def push(self, input_terms):
        step, state, action, reward, next_state, done, debug_term = input_terms
        if self.userDefinedSettings.LSTM_FLAG:
            current_buffer_index = step
        else:
            current_buffer_index = 0

        self.state_buffer.push(state, current_buffer_index)
        self.action_buffer.push(action, current_buffer_index)
        self.reward_buffer.push(reward, current_buffer_index)
        self.next_state_buffer.push(next_state, current_buffer_index)
        self.done_buffer.push(done, current_buffer_index)
        self.debug_buffer.push(done, current_buffer_index)

    def sample(self, batch_size=None, sampling_method='random', batch_index=None):
        state_sequence_batch = self.state_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        action_sequence_batch = self.action_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        next_state_sequence_batch = self.next_state_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        reward_sequence_batch = self.reward_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        done_sequence_batch = self.done_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        debug_sequence_batch = self.debug_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)

        if not self.userDefinedSettings.LSTM_FLAG:
            sequence_axis = 1
            state_sequence_batch = state_sequence_batch.squeeze(sequence_axis)
            action_sequence_batch = action_sequence_batch.squeeze(sequence_axis)
            next_state_sequence_batch = next_state_sequence_batch.squeeze(sequence_axis)
            reward_sequence_batch = reward_sequence_batch.squeeze(sequence_axis)
            done_sequence_batch = done_sequence_batch.squeeze(sequence_axis)
            debug_sequence_batch = debug_sequence_batch.squeeze(sequence_axis)

        return state_sequence_batch, action_sequence_batch, reward_sequence_batch, next_state_sequence_batch, done_sequence_batch, debug_sequence_batch

    def __len__(self):
        return len(self.state_buffer)


class LSTMMemory(object):
    def __init__(self, STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings):
        memory_size = int(userDefinedSettings.memory_size / MAX_EPISODE_LENGTH)
        SEQUENCE_LENGTH = MAX_EPISODE_LENGTH
        self.last_action_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[ACTION_DIM], userDefinedSettings=userDefinedSettings)
        self.hidden_in_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=1, STEP_DATA_SHAPE=[userDefinedSettings.HIDDEN_NUM], userDefinedSettings=userDefinedSettings, is_lstm_hidden=True)
        self.hidden_out_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=1, STEP_DATA_SHAPE=[userDefinedSettings.HIDDEN_NUM], userDefinedSettings=userDefinedSettings, is_lstm_hidden=True)
        self.cell_in_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=1, STEP_DATA_SHAPE=[userDefinedSettings.HIDDEN_NUM], userDefinedSettings=userDefinedSettings, is_lstm_hidden=True)
        self.cell_out_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=1, STEP_DATA_SHAPE=[userDefinedSettings.HIDDEN_NUM], userDefinedSettings=userDefinedSettings, is_lstm_hidden=True)

    def clear(self):
        self.last_action_buffer.clear()
        self.hidden_in_buffer.clear()
        self.hidden_out_buffer.clear()
        self.cell_in_buffer.clear()
        self.cell_out_buffer.clear()

    def push(self, input_terms):
        step, lstm_term = input_terms
        current_buffer_index = step

        self.last_action_buffer.push(lstm_term['last_action'], current_buffer_index)
        if step == 0:
            hidden_in, cell_in = lstm_term['hidden_in']
            hidden_out, cell_out = lstm_term['hidden_out']
            self.hidden_in_buffer.push(hidden_in, current_buffer_index)
            self.hidden_out_buffer.push(hidden_out, current_buffer_index)
            self.cell_in_buffer.push(cell_in, current_buffer_index)
            self.cell_out_buffer.push(cell_out, current_buffer_index)

    def sample(self, batch_size=None, sampling_method='random', batch_index=None):
        last_action_sequence_batch = self.last_action_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        hidden_in_batch = self.hidden_in_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        hidden_out_batch = self.hidden_out_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        cell_in_batch = self.cell_in_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        cell_out_batch = self.cell_out_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)

        hidden_in = (hidden_in_batch[None, ...], cell_in_batch[None, ...])
        hidden_out = (hidden_out_batch[None, ...], cell_out_batch[None, ...])
        lstm_term = {'hidden_in': hidden_in, 'hidden_out': hidden_out, 'last_action': last_action_sequence_batch}
        return lstm_term

    def __len__(self):
        return len(self.last_action_buffer)


class DomainMemory(object):
    def __init__(self, STATE_DIM, ACTION_DIM, MAX_EPISODE_LENGTH, DOMAIN_PARAMETER_DIM, userDefinedSettings):
        self.userDefinedSettings = userDefinedSettings
        if userDefinedSettings.LSTM_FLAG:
            memory_size = int(userDefinedSettings.memory_size / MAX_EPISODE_LENGTH)
            SEQUENCE_LENGTH = MAX_EPISODE_LENGTH
        else:
            memory_size = int(userDefinedSettings.memory_size)
            SEQUENCE_LENGTH = 1
        self.domain_parameter_buffer = MemoryTerm(MAX_MEMORY_SIZE=memory_size, SEQUENCE_LENGTH=SEQUENCE_LENGTH, STEP_DATA_SHAPE=[DOMAIN_PARAMETER_DIM], userDefinedSettings=userDefinedSettings)

    def clear(self):
        self.domain_parameter_buffer.clear()

    def push(self, input_terms):
        step, domain_parameter = input_terms
        if self.userDefinedSettings.LSTM_FLAG:
            current_buffer_index = step
        else:
            current_buffer_index = 0
        self.domain_parameter_buffer.push(domain_parameter, current_buffer_index)

    def sample(self, batch_size=None, sampling_method='random', batch_index=None):
        domain_parameter_batch = self.domain_parameter_buffer.sample(batch_size=batch_size, sampling_method=sampling_method, index=batch_index)
        if not self.userDefinedSettings.LSTM_FLAG:
            sequence_axis = 1
            domain_parameter_batch = domain_parameter_batch.squeeze(sequence_axis)
        return domain_parameter_batch

    def __len__(self):
        return len(self.domain_parameter_buffer)


class MemoryTerm(object):
    def __init__(self, MAX_MEMORY_SIZE, SEQUENCE_LENGTH, STEP_DATA_SHAPE, userDefinedSettings, is_lstm_hidden=False):
        self.userDefinedSettings = userDefinedSettings
        self.MAX_MEMORY_SIZE = MAX_MEMORY_SIZE
        self.SEQUENCE_LENGTH = SEQUENCE_LENGTH
        self.buffer = CircularQueue(MAX_MEMORY_SIZE=MAX_MEMORY_SIZE, DATA_SHAPE=[SEQUENCE_LENGTH, *STEP_DATA_SHAPE], is_lstm_hidden=is_lstm_hidden)
        self.episode_data = []

    def clear(self):
        self.buffer.clear_queue()

    def push(self, data, current_buffer_index):
        self.episode_data.append(data)
        if len(self.episode_data) >= self.SEQUENCE_LENGTH:
            assert len(self.episode_data) == current_buffer_index + 1, 'pushing episode data is shifted'
            self.push_episode()
            self.episode_memory_reset()

    def push_episode(self):
        self.buffer.append(self.episode_data)

    def episode_memory_reset(self):
        self.episode_data.clear()

    def sample(self, batch_size=None, sampling_method='random', index=None):
        state_sequence_batch = torch.FloatTensor(self.buffer.get(size=batch_size, how=sampling_method, index=index)).to(self.userDefinedSettings.DEVICE)
        return state_sequence_batch

    def __len__(self):
        return len(self.buffer)


class CircularQueue(object):
    def __init__(self, MAX_MEMORY_SIZE, DATA_SHAPE, dtype=np.float32, is_lstm_hidden=False):
        self.MAX_MEMORY_SIZE = MAX_MEMORY_SIZE
        self.DATA_SHAPE = DATA_SHAPE
        self.dtype = dtype
        self.is_lstm_hidden = is_lstm_hidden
        self.clear_queue()

    def clear_queue(self):
        self.circular_queue = np.empty((self.MAX_MEMORY_SIZE, *self.DATA_SHAPE), dtype=self.dtype)
        self.current_queue_index = 0
        self.current_queue_size = 0

    def append(self, data):
        if self.is_lstm_hidden:
            formated_data = data[0].cpu().detach().numpy().reshape(1, -1)
        else:
            formated_data = np.array(data, dtype=self.dtype)
            if len(formated_data.shape) == 1:
                formated_data = formated_data.reshape(-1, 1)
        self.circular_queue[self.current_queue_index] = formated_data
        self.set_next_queue_index()

    def set_next_queue_index(self):
        if self.current_queue_size == self.MAX_MEMORY_SIZE - 1:
            self.current_queue_index = 0
            self.current_queue_size += 1
        elif self.current_queue_size < self.MAX_MEMORY_SIZE - 1:
            self.current_queue_index += 1
            self.current_queue_size += 1
        elif self.current_queue_index >= self.MAX_MEMORY_SIZE - 1:
            self.current_queue_index = 0
        else:
            self.current_queue_index += 1

    def get(self, size, how='random', index=None):
        if index is not None:
            data = self.circular_queue[index]
        elif how == 'random':
            data = self.get_random(size)
        elif how == 'last':
            data = self.get_last(size)
        else:
            assert False, 'choose correct sampling method of replay memory'

        if self.is_lstm_hidden:
            sequence_index = 1
            data = data.squeeze(sequence_index)
        return data

    def get_random(self, size):
        index = np.random.randint(low=0, high=len(self.circular_queue), size=size)
        return self.circular_queue[index]

    def get_last(self, size):
        if self.current_queue_index - size < 0:
            remain = size - self.current_queue_index + 1
            return np.concatenate([self.circular_queue[:self.current_queue_index], self.circular_queue[-remain + 1:]])
        else:
            return self.circular_queue[-size:]

    def __len__(self):
        return self.current_queue_size

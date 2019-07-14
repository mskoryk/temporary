import random
import torch
from . import solutionmanager as sm
import numpy as np

class GridSearch():
    GRID_LIST_SUFFIX = '_grid'
    GRID_PARAM_SEPARATOR = ' '
    GRID_VALUE_SEPARATOR = '-'

    def __init__(self):
        self = self

    def get_grid_attributes(self, solution):
        s = solution
        return {self.get_grid_attribute(s, a): self.get_grid_attribute_list(s, a) for a in dir(s) if self.filter_grid_attribute(s, a)}

    def get_grid_attribute(self, obj, attr):
        return attr[:-len(GridSearch.GRID_LIST_SUFFIX)]

    def get_grid_attribute_list(self, obj, attr):
        return getattr(obj, attr)

    def filter_grid_attribute(self, obj, attr):
        return attr.endswith(GridSearch.GRID_LIST_SUFFIX) and not attr.startswith('__') and not callable(getattr(obj,attr))

    def calc_grid_size(self, grid_attributes):
        grid_size = 1
        for attr, attr_list in grid_attributes.items():
            grid_size *= len(attr_list)
        return grid_size

    def grid_choice_to_str(self, grid_choice):
        grid_str = ''
        for attr, attr_value in grid_choice.items():
            if len(grid_str):
                grid_str += GridSearch.GRID_PARAM_SEPARATOR
            grid_str += attr + GridSearch.GRID_VALUE_SEPARATOR + str(attr_value)
        return grid_str

    def get_grid_choice(self, grid_attributes, grid_choice_history, random_order):
        history_size = len(grid_choice_history)
        while True:
            grid_choice = {}
            choice_ind = history_size
            for attr, attr_list in grid_attributes.items():
                attr_list_size = len(attr_list)
                if random_order:
                    attr_ind = random.randint(0, attr_list_size-1)
                else:
                    attr_ind = choice_ind%attr_list_size
                    choice_ind //= attr_list_size
                grid_choice[attr] = attr_list[attr_ind]
            choice_str = self.grid_choice_to_str(grid_choice)
            if choice_str not in grid_choice_history:
                return choice_str, grid_choice

    def set_grid_choice(self, solution, choice_str, grid_choice):
        self.choice_str = choice_str
        for attr, attr_value in grid_choice.items():
            setattr(solution, attr, attr_value)

    def add_result(self, name, value):
        if not hasattr(self, 'results_cache'):
            self.results_cache = {}
        if name not in self.results_cache:
            self.results_cache[name] = {}
        if self.choice_str not in self.results_cache[name]:
            self.results_cache[name][self.choice_str] = []
        self.results_cache[name][self.choice_str].append(value)

    def get_results(self, name):
        return self.results_cache[name][self.choice_str]

    def get_stats(self, name, no_last=0):
        results = self.get_results(name)
        t = torch.FloatTensor(results)
        if no_last > 0:
            t = t.sort()[0][:-no_last]
        return t.mean().item(), t.std().item()

    def get_all_results(self, name):
        return self.results_cache[name]

    def get_iter_number(self, solution):
        if hasattr(solution, 'iter_number'):
            return solution.iter_number
        else:
            return 1

    def run(self, config, case_number, random_order=False, verbose=False):
        solution = config.get_solution()
        solution.grid_search = self
        grid_attributes = self.get_grid_attributes(solution)
        grid_size = self.calc_grid_size(grid_attributes)
        iter_number = self.get_iter_number(solution)
        if verbose:
            print('[Grid search] Running: grid_size={} iter_number={} verbose={}'.format(grid_size, iter_number, verbose))
        grid_choice_history = {}
        solution_manager = sm.SolutionManager()
        data_provider = config.get_data_provider()
        best_solution = None 
        while len(grid_choice_history) <  grid_size:
            solution_manager.print_hint("\n\nRunning {} iteration out of {}". format(len(grid_choice_history), grid_size))
            choice_str, grid_choice = self.get_grid_choice(grid_attributes, grid_choice_history, random_order)
            
            self.set_grid_choice(solution, choice_str, grid_choice)
            is_good_combo = True
            results = []                       
            for iter in range(iter_number):                
                case_data = data_provider.create_case_data(iter+1)
                if verbose:
                    print('[Grid search] Running: choise_str={} iter={}'.format(choice_str, iter))
                solution.iter = iter
                # solution_manager.train_model(iter, solution, case_data)
                init_seed = iter + 1
                step, execution_time, reject_reason, model = solution_manager.train_model(init_seed, solution, case_data)
                model_size = solution_manager.calc_model_size(model)
                model.eval()
                data, target = case_data.train_data
                train_stat = solution_manager.calc_model_stats(config, model, data, target)
                data, target = case_data.test_data
                test_stat = solution_manager.calc_model_stats(config, model, data, target)
                case_result = {
                        'case': case_data.number,
                        'step': step,
                        'time': execution_time,
                        'reject_reason': reject_reason,
                        'size': model_size,
                        'trainStat': train_stat,
                        'testStat': test_stat
                        }
                case_result['description'] = case_data.description
                case_result = solution_manager.evaluate_result(case_data, case_result, verbose=False)
                if case_result['accepted'] == False:
                    is_good_combo = False
                    break
                results.append(case_result)
            if is_good_combo:
                print(solution_manager.accepted_string("[OK]") + ': choise_str={}'.format(choice_str))
                # current_steps = np.mean([steps['step'] for steps in results])
                current_time = np.mean([steps['time'] for steps in results])
                # solution_manager.print_hint("average number of steps is " + str(current_steps))    
                if not best_solution:
                    best_solution = {}
                    # best_solution['steps'] = current_steps
                    best_solution['time'] = current_time
                    best_solution['params'] = 'choise_str={}'.format(choice_str)
                    
                else:
                    if best_solution['time'] > current_time:
                        best_solution['time'] = current_time
                        best_solution['params'] = 'choise_str={}'.format(choice_str)
            else:
                print(solution_manager.rejected_string("[REJECTED]") + ': choise_str={} iter={}'.format(choice_str, iter))

            grid_choice_history[choice_str] = True
        print(solution_manager.accepted_string("[SEARCH COMPLETED]"))
        if best_solution:
            print(solution_manager.accepted_string("[BEST_FOUND_SOLUTION]"))
            print(best_solution['params'])
            print(best_solution['time'])            
        print("Specify case_number, if you want to search over other case data")

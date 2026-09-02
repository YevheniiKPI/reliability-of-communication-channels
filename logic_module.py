import numpy as np
from collections import deque
import math

#Клас Ребер, що зберігає координати ребра між двома вершинами
class Edge:
    def __init__(self, i, j, pr, pb):
        self.i = i
        self.j = j
        self.price = pr
        self.probability = pb

#Клас Вершин, що зберігає номер вершини та чи була вона відвідана
class Vertex:
    def __init__(self, idx):
        self.idx = idx
        self.was_visited = False

# Головна функція, що містить всі функції
def brute_force(m, p, pb, pr):
    max_vertexes = m
    max_price = p
    probability_matrix = pb
    price_matrix = pr

    current_min = 0.0
    vertexes = []
    edges = []

    for i in range(0, max_vertexes):
        vertexes.append(Vertex(i))
        for j in range(i + 1, max_vertexes):
            if not price_matrix[i][j] == 0.0 or not probability_matrix[i][j] == 0.0:
                edges.append(Edge(i, j, price_matrix[i][j], probability_matrix[i][j]))

    queue_adj_matrix = deque()
    adj_matrix = np.zeros((max_vertexes, max_vertexes), dtype=int)

    result_adj_matrix = np.zeros((max_vertexes, max_vertexes), dtype=int)
    result_reliability_matrix = np.zeros((max_vertexes, max_vertexes))

    # Генерація всіх варіантів матриці суміжності
    def generateGraphs(i, price, edge_count):
        if price > max_price:
            return
        
        if i == len(edges):
            if edge_count < max_vertexes - 1: return
            if checkComponent() == True:
                #processGraph()
                queue_adj_matrix.append(adj_matrix.copy())
            return

        adj_matrix[edges[i].i][edges[i].j] = 1
        adj_matrix[edges[i].j][edges[i].i] = 1
        generateGraphs(i + 1, price + price_matrix[edges[i].i][edges[i].j], edge_count + 1)

        adj_matrix[edges[i].i][edges[i].j] = 0
        adj_matrix[edges[i].j][edges[i].i] = 0
        generateGraphs(i + 1, price, edge_count)

    # Перевірка чи всі вершини мають хоча б одне ребро (Пошук в ширину)
    def checkComponent():
        q = deque()
        visited = [False] * max_vertexes

        q.append(0)
        visited[0] = True

        sum = 1
        while not len(q) == 0:
            current = q.popleft()

            for x in range(0, max_vertexes):
                if adj_matrix[current][x] == 1 and not visited[x]:
                    visited[x] = True
                    q.append(x)
                    sum+=1
        return sum == max_vertexes

    # Розрахунок ймовірності та надійності кожного шляху між всіма вершинами
    def processGraph(matrix):
        p = []
        temp_probability_matrix = np.zeros((max_vertexes, max_vertexes))

        for i in range(0, max_vertexes):
            for j in range(i + 1, max_vertexes):
                calculateProbability(vertexes[i], vertexes[j], 1.0, p, matrix)
                calculateReliability(vertexes[i].idx, vertexes[j].idx, p, temp_probability_matrix)
                p.clear()

        checkMin(temp_probability_matrix, matrix)

    # Обрахування ймовірності одного шляху між двома вершинами (Пошук в глибину)
    def calculateProbability(start, end, pij, p, matrix):
        vertexes[start.idx].was_visited = True
        if start.idx == end.idx:
            p.append(pij)
        else:
            for i in range(0, max_vertexes):
                if matrix[start.idx][i] == 1 and not vertexes[i].was_visited:
                    calculateProbability(vertexes[i], end, pij * probability_matrix[start.idx][i], p, matrix)
        vertexes[start.idx].was_visited = False

    # Обрахування надійності одного елементу матриці
    def calculateReliability(i, j, p, temp_probability_matrix):
        result = 1.0
        for k in range(0, len(p)):
            result *= 1 - p[k]
        r = 1 - result
        temp_probability_matrix[i][j] = r
        temp_probability_matrix[j][i] = r

    # Перевірка чи локальний мінімальний елемент матриці більший за глобальний мінімум  
    def checkMin(temp_probability_matrix, matrix):
        nonlocal current_min, result_adj_matrix, result_reliability_matrix
        min_temp = temp_probability_matrix[0][1]
        for i in range(0, max_vertexes):
            for j in range(i + 1, max_vertexes):
                if temp_probability_matrix[i][j] < min_temp:
                    min_temp = temp_probability_matrix[i][j]

        if min_temp > current_min:
            current_min = min_temp
            result_adj_matrix = matrix.copy()
            result_reliability_matrix = temp_probability_matrix.copy()

    generateGraphs(0, 0, 0)

    for matrix in queue_adj_matrix:
        processGraph(matrix)

    return result_adj_matrix, result_reliability_matrix

def optimal_algorithm(m, p, pb, pr):
    max_vertexes = m
    max_price = p
    probability_matrix = pb
    price_matrix = pr

    vertexes = []
    edges = []
    for i in range(0, max_vertexes):
        vertexes.append(Vertex(i))
        for j in range(i + 1, max_vertexes):
            if not price_matrix[i][j] == 0.0 or not probability_matrix[i][j] == 0.0:
                edges.append(Edge(i, j, price_matrix[i][j], probability_matrix[i][j]))

    def binary_search():
        result = None
        edges.sort(key=lambda edge: edge.probability)

        low = 0
        high = len(edges) - 1
        while low <= high:
            mid = math.floor((low + high) / 2)
            mid_element = edges[mid]

            found, adj_matrix = kruskal(mid_element)
            if found:
                result = adj_matrix
                low = mid + 1
            else:
                high = mid - 1
        return result

    def kruskal(mid_element):
        temp_adj_matrix = np.zeros((max_vertexes, max_vertexes), dtype=int)
        temp_edges = []
        for edge in edges:
            if edge.probability >= mid_element.probability:
                temp_edges.append(edge)

        temp_edges.sort(key=lambda edge: edge.price)

        parent = [None] * max_vertexes

        for i in range(0, max_vertexes):
            parent[i] = i

        count = 0
        i = 0
        price = 0
        while count < max_vertexes - 1 and i < len(temp_edges):
            edge = temp_edges[i]
            i += 1
            u = edge.i
            v = edge.j
            pu = find(parent, u)
            pv = find(parent, v)
            if pu != pv:
                count += 1
                temp_adj_matrix[u][v] = 1
                temp_adj_matrix[v][u] = 1
                parent[pu] = pv
                price += edge.price
            if price > max_price:
                return False, None

        if count == max_vertexes - 1:
            return True, temp_adj_matrix

        return False, None

    def find(parent, i):
        if parent[i] != i:
            parent[i] = find(parent, parent[i])
        return parent[i]

    def calculate_matrix():
        p = []
        reliable_matrix = np.zeros((max_vertexes, max_vertexes))
        for i in range(0, max_vertexes):
            for j in range(i + 1, max_vertexes):
                calculate_probability(vertexes[i], vertexes[j], 1.0, p, result_adj_matrix)
                calculate_reliability(i, j, p, reliable_matrix)
                p.clear()
        return reliable_matrix

    def calculate_probability(start, end, pij, p, matrix):
        vertexes[start.idx].was_visited = True
        if start.idx == end.idx:
            p.append(pij)
        else:
            for i in range(0, max_vertexes):
                if matrix[start.idx][i] == 1 and not vertexes[i].was_visited:
                    calculate_probability(vertexes[i], end, pij * probability_matrix[start.idx][i], p, matrix)
        vertexes[start.idx].was_visited = False
    
    def calculate_reliability(i, j, p, reliable_matrix):
        result = 1.0
        for k in range(0, len(p)):
            result *= 1 - p[k]
        r = 1 - result
        reliable_matrix[i][j] = reliable_matrix[j][i] = r

    result_adj_matrix = binary_search()
    if result_adj_matrix is None:
        return None, None
    result_reliable_matrix = calculate_matrix()
    return result_adj_matrix, result_reliable_matrix
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.optimize import minimize
import pandas_datareader.data as web
import statsmodels.api as sm
import matplotlib.pyplot as plt



# USER INPUTS SECTION
end_date = datetime.today()
years = int(input('Enter the number of years you want to take into consideration (e.g : 5) : '))
start_date = end_date - timedelta(years*365)

tickers = input('Enter the assets you own by their tickers and separated by a comma (e.g : AMZN, AAPL, NVDA, GOOGL) : ')
ticker_list = tickers.split(sep=',')
ticker_list = [t.strip() for t in ticker_list]

weights = input('Enter your allocation for each asset separated by a comma (e.g : 0.25,0.25,0.25,0.25) : ')
weights_list = weights.split(',')
initial_weights = list(map(float, weights_list))

if not np.isclose(np.sum(initial_weights), 1):
    raise ValueError("Your allocation isn't equal to 1, please retype it.")

nb_sim = int(input('Enter the number of simulations desired for the Monte Carlo method. (1000 to 100000) :'))

tickers_data = yf.download(ticker_list, start_date, end_date)





def fama_french5(end_date=end_date, start_date=start_date, ticker_list=ticker_list, tickers_data=tickers_data, initial_weights=initial_weights):
    """
    Fama French 5 Factors Model function returning each 5 betas, R-squared & Adjusted R-squared through a plot.
    """

    ff_data = web.DataReader('F-F_Research_Data_5_Factors_2x3', 'famafrench', start= start_date, end= end_date)

    monthly_factors = ff_data[0]                    # MONTHLY DATA
    monthly_factors.head()
    updated_factors = monthly_factors.div(100)
    updated_factors.index = updated_factors.index.to_timestamp().to_period('M')

    monthly_tickers = tickers_data.resample('M').last()
    monthly_returns = monthly_tickers.pct_change()
    monthly_returns['Close']

    # PORTFOLIO RETURNS CALCULUS
    portfolio_returns = (monthly_returns['Close'] * initial_weights).sum(axis=1)
    portfolio_avg_return = portfolio_returns.mean()

    # STANDARDIZING INDEXES
    portfolio_returns.index = portfolio_returns.index.to_period('M')
    common_index = portfolio_returns.index.intersection(updated_factors.index)
    portfolio_returns = portfolio_returns.loc[common_index]
    updated_factors = updated_factors.loc[common_index]

    common_idx = portfolio_returns.index.intersection(updated_factors.index)
    portfolio_returns = portfolio_returns.loc[common_idx]
    updated_factors = updated_factors.loc[common_idx]

    portfolio_exreturns = portfolio_returns - monthly_factors['RF'].loc[common_idx]

    # X/Y ALIGNEMENT
    factors = updated_factors[['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']]
    X = sm.add_constant(factors)
    Y = portfolio_exreturns

    reg = sm.OLS(Y,X)
    results = reg.fit()
    results.params
    results.summary()

    alpha = results.params['const']  
    betas = results.params.drop('const')
    final_factors = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']
    betas = betas[final_factors]

    # PLOTTING
    betas.plot(kind='bar', figsize=(12,6),)
    plt.ylabel('Betas coefficient')
    plt.title('Portfolio Returns Explanation – Fama-French 5 Factor Model')

    # R-SQUARED & ADJUSTED R-SQUARED
    r_squared = results.rsquared * 100
    r_squared_adj = results.rsquared_adj * 100
    x_pos = plt.xlim()[1] * 1.01   
    y_pos = plt.ylim()[1] * 0.9   
    plt.text(x=x_pos, y=y_pos,
            s=f"R² = {r_squared:.2f}%\nAdj. R² = {r_squared_adj:.2f}%",
            fontsize=12,
            ha='left', va='top',
            bbox=dict(facecolor="white", alpha=0.7))
    plt.subplots_adjust(left=0.095, right=0.86)

    return plt





def monte_carlo_sim(end_date=end_date, start_date=start_date, ticker_list=ticker_list, tickers_data=tickers_data, initial_weights=initial_weights, nb_sim=nb_sim):
    """
    Monte Carlo Simulation function returning the Value at Risk (VaR) and Conditional Value at Risk (CVaR) through a plot.
    """
    
    returns = tickers_data['Close'].pct_change().dropna()
    mean_returns = returns.mean()
    cov_matrix = returns.cov()
    returns['portfolio'] = returns @ initial_weights
    expected_returns = np.sum(mean_returns * initial_weights) * 252

    # SIMULATION SECTION
    time = 252
    mean_returns_matrix = np.tile(mean_returns.values, (time, 1)).T
    portfolio_simulation = np.zeros(shape=(time, nb_sim))

    for i in range(0, nb_sim):
        correlated_random_returns = np.random.multivariate_normal(mean_returns, cov_matrix, time)
        portfolio_simulation[:, i] = np.cumprod(np.inner(initial_weights, correlated_random_returns) + 1) * 1000

    # CALCULUS SECTION
    def mc_VaR(returns,alpha=5):
        if isinstance(returns, pd.Series):
            return np.percentile(returns,alpha)
        else:
            return TypeError('Expected a pandas data series')

    def mc_CVaR(returns,alpha=5):
        if isinstance(returns, pd.Series):
            below_var = returns <= mc_VaR(returns, alpha=alpha)
            return returns[below_var].mean()
        else:
            return TypeError('Expected a pandas data series')

    # RESULTS SECTION WITH A PORTFOLIO VALUE OF 1000
    portfolio_results = pd.Series(portfolio_simulation[-1,:])
    var = (1000 - mc_VaR(portfolio_results, alpha=5)) / 1000 * 100
    cvar = (1000 - mc_CVaR(portfolio_results, alpha=5)) / 1000 * 100

    plt.figure(figsize=(12, 6))
    plt.plot(portfolio_simulation)
    plt.title('Monte Carlo Simulation')
    plt.xlabel('Time over one year of trading (252d)')
    plt.ylabel('Portfolio Value in $')
    # VAR AND CVAR SECTION
    plt.text(x=len(portfolio_simulation)*1.1, y=portfolio_simulation.max()*0.9,
            s=f"VaR: {var:.2f}%\nCVaR: {cvar:.2f}%\nSimulation through \n{nb_sim} iterations",
            fontsize=12, bbox=dict(facecolor="white", alpha=0.7))
    plt.tight_layout()
    # VAR (5TH FINAL PERCENTILE LINE)
    plt.axhline(y=mc_VaR(portfolio_results, alpha=5), color='black', linewidth=1, label='VaR (Confidence level : 5%)')
    plt.legend()

    return plt





def efficient_frontier(end_date=end_date, start_date=start_date, ticker_list=ticker_list, tickers_data=tickers_data, initial_weights=initial_weights):
    """
    Harry Markowitz's Efficient Frontier function returning both Initial and Optimal Portfolios with their own sepcs
    (portfolofio's allocation, Expected return, Volatility, Beta & it's Sharpe ratio) through a plot.
    """

    initial_weights = np.array(initial_weights)

    tickers_data = tickers_data['Close'].dropna()
    tickers_data.columns = ticker_list

    log_returns = np.log(tickers_data / tickers_data.shift(1)).dropna()
    trading_days = 252
    average_log_returns = log_returns.mean() * trading_days
    sigma = log_returns.cov() * trading_days

    # SIMULATION & CALCULUS SECTION
    n = len(ticker_list)
    nb_portfolio = 50000
    weights = []
    exp_returns = []
    exp_vol = []
    sharpe_ratio = []

    for _ in range(nb_portfolio):
        w = np.random.random(n)
        w = w / np.sum(w)
        weights.append(w)
        exp_r = np.sum(average_log_returns * w)
        exp_v = np.sqrt(np.dot(w.T, np.dot(sigma, w)))
        exp_returns.append(exp_r)
        exp_vol.append(exp_v)
        sharpe_ratio.append(exp_r / exp_v)

    exp_returns = np.array(exp_returns)
    exp_vol = np.array(exp_vol)
    sharpe_ratio = np.array(sharpe_ratio)
    weights = np.array(weights)
    max_index = sharpe_ratio.argmax()
    optimal_weights = weights[max_index]

    # CALCULUS BIS SECTION
    def portfolio_beta(weights, log_returns, market_returns):
        port_ret = log_returns @ weights
        aligned = pd.concat([port_ret, market_returns], axis=1, join='inner').dropna()
        if aligned.shape[0] == 0:
            return np.nan
        cov = np.cov(aligned.iloc[:,0], aligned.iloc[:,1])[0,1]
        var = np.var(aligned.iloc[:,1])
        return cov / var

    # S&P500 REFERENCE MARKET FOR BETA CALCULUS
    market = yf.download('^GSPC', start=start_date, end=end_date)['Close'].dropna()
    market_log_returns = np.log(market / market.shift(1)).dropna().loc[log_returns.index]

    # INITIAL PORTFOLIO
    init_return = np.sum(average_log_returns * initial_weights)
    init_vol = np.sqrt(np.dot(initial_weights.T, np.dot(sigma, initial_weights)))
    init_sharpe = init_return / init_vol
    init_beta = portfolio_beta(initial_weights, log_returns, market_log_returns)

    # OPTIMAL PORTFOLIO
    opt_return = np.sum(average_log_returns * optimal_weights)
    opt_vol = np.sqrt(np.dot(optimal_weights.T, np.dot(sigma, optimal_weights)))
    opt_sharpe = opt_return / opt_vol
    opt_beta = portfolio_beta(optimal_weights, log_returns, market_log_returns)

    # PLOTTING SECTION
    plt.figure(figsize=(12,6))
    plt.scatter(exp_vol, exp_returns, c=sharpe_ratio, cmap='viridis', alpha=0.5)
    plt.colorbar(label='Sharpe Ratio')
    plt.scatter(init_vol, init_return, c='black', marker='o', s=80, label='Initial Portfolio')
    plt.scatter(opt_vol, opt_return, c='red', marker='*', s=120, label='Max Sharpe Portfolio')
    plt.xlabel('Volatility (Std Dev)')
    plt.ylabel('Expected Return')
    plt.title("Harry Markowitz's Efficient Frontiere")
    plt.legend()
    plt.subplots_adjust(left=0.075)

    init_text = "Initial Portfolio\n\n" + "\n".join([f"{t}: {w*100:.2f}%" for t, w in zip(ticker_list, initial_weights)]) + "\n\n" + \
    f"Exp. Return: {init_return:.2%}\nVolatility: {init_vol:.2%}\nBeta: {init_beta:.2f}\nSharpe: {init_sharpe:.2f}"
    opt_title = r"$\bf{Portefeuille\ optimal}$"
    opt_alloc = "\n" + "\n".join([f"{t}: {w*100:.2f}%" for t, w in zip(ticker_list, optimal_weights)]) + "\n\n"
    opt_metrics = f"Exp. Return: {opt_return:.2%}\nVolatility: {opt_vol:.2%}\nBeta: {opt_beta:.2f}\nSharpe: {opt_sharpe:.2f}"
    opt_text = "Optimal Portfolio\n\n" + "\n".join(
        [f"{t}: {w*100:.2f}%" for t, w in zip(ticker_list, optimal_weights)]
    ) + "\n\n" + \
    f"Exp. Return: {opt_return:.2%}\nVolatility: {opt_vol:.2%}\nBeta: {opt_beta:.2f}\nSharpe: {opt_sharpe:.2f}"
    
    plt.gcf().text(
        0.975, 0.85, init_text, fontsize=9, va='top', ha='right',
        bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=1))
    plt.gcf().text(
        0.975, 0.4, opt_text, fontsize=9, va='top', ha='right',
        bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="red", lw=1))

    # CAPITAL MARKET LINE (CML)
    risk_free_rate = 0.02  # 2%
    cml_x = np.linspace(0, max(exp_vol)*1.1, 100)
    cml_slope = (opt_return - risk_free_rate) / opt_vol
    cml_y = risk_free_rate + cml_slope * cml_x
    plt.plot(cml_x, cml_y, color='green', linestyle='--', label='Capital Market Line (CML)')

    # EFFICIENT FRONTIER LINE PLOTTING
    def minimize_volatility(target_return, average_log_returns, sigma):
        n = len(average_log_returns)
        constraints = (
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
            {'type': 'eq', 'fun': lambda w: np.sum(average_log_returns * w) - target_return}
        )
        bounds = tuple((0, 1) for _ in range(n))
        initial_guess = np.repeat(1/n, n)
        result = minimize(
            lambda w: np.sqrt(np.dot(w.T, np.dot(sigma, w))),
            initial_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        return result

    returns_range = np.linspace(exp_returns.min(), exp_returns.max(), 50)
    efficient_vol = []
    efficient_ret = []
    for r in returns_range:
        res = minimize_volatility(r, average_log_returns, sigma)
        if res.success:
            efficient_vol.append(res.fun)
            efficient_ret.append(r)

    plt.plot(efficient_vol, efficient_ret, color='black', linewidth=2, label='Frontière efficiente')
    plt.legend()
    
    return plt






fama_french5()
monte_carlo_sim()
efficient_frontier()
plt.show()
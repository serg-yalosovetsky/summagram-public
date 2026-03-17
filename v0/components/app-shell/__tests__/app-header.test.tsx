import { render, screen, fireEvent } from '@testing-library/react';
import { AppHeader } from '../app-header';
import { useApp } from '../app-context';

// Mock the useApp hook
jest.mock('../app-context', () => ({
    useApp: jest.fn(),
}));

describe('AppHeader', () => {
    const mockToggleDebugPanel = jest.fn();

    beforeEach(() => {
        (useApp as jest.Mock).mockReturnValue({
            toggleDebugPanel: mockToggleDebugPanel,
            debugPanelOpen: false,
        });
    });

    it('renders the application name', () => {
        render(<AppHeader />);
        expect(screen.getByText('summagram')).toBeInTheDocument();
        expect(screen.getByText('version 0.1')).toBeInTheDocument();
    });

    it('calls toggleDebugPanel when the debug button is clicked', () => {
        render(<AppHeader />);
        const debugButton = screen.getByLabelText('Toggle debug panel');
        fireEvent.click(debugButton);
        expect(mockToggleDebugPanel).toHaveBeenCalledTimes(1);
    });

    it('applies active class when debug panel is open', () => {
        (useApp as jest.Mock).mockReturnValue({
            toggleDebugPanel: mockToggleDebugPanel,
            debugPanelOpen: true,
        });
        render(<AppHeader />);
        const debugButton = screen.getByLabelText('Toggle debug panel');
        expect(debugButton).toHaveClass('bg-primary/15');
    });
});

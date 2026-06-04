import { ReactNode, useEffect } from 'react'
import { Navigate } from 'react-router'
import { useAppSelector, useAppDispatch } from '../store'
import { setUser, logout } from '../store/authSlice'
import { useGetMeQuery } from '../store/api'

interface ProtectedRouteProps {
  children: ReactNode
  requiredRoles?: string[]
}

export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAppSelector((state) => state.auth)
  const dispatch = useAppDispatch()
  const { data: me, error } = useGetMeQuery(undefined, { skip: !isAuthenticated })

  useEffect(() => {
    if (me) {
      dispatch(setUser(me))
    }
    if (error) {
      dispatch(logout())
    }
  }, [me, error, dispatch])

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (requiredRoles && user) {
    const hasRole = requiredRoles.some((role) => user.roles.includes(role))
    if (!hasRole) {
      return <Navigate to="/" replace />
    }
  }

  return <>{children}</>
}
